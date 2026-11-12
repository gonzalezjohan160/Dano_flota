from conexiones import transaccion
from repositories.flota import consultar_tipologia
from repositories.sesiones import sesion_bd
from contextlib import closing
from flask import Blueprint, request, render_template, jsonify
from datetime import datetime, timedelta
from config import connect
import requests
from backend_security import usuario_id_sesion
from backend_security import (
    login_required,
    requiere_permiso,
    usuario_puede_acceder_uf,
    ufs_autorizadas_sesion,
)
from pathlib import Path
from werkzeug.utils import secure_filename
from config import BASE_DIR
from config import UPLOAD_FOLDERS
from attachment_security import (
    AttachmentValidationError,
    store_upload,
    validate_uploads,
)
from logger import logger
from modelos import capturador as modelo_capturador
from modelos import catalogos as modelo_catalogos
from modelos import flota as modelo_flota
from servicios.validacion_caso import area_del_operador, error_de_catalogo


Capturador = Blueprint(
    "Capturador",                                   # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR / "frontend"),
    static_folder=str(BASE_DIR / "Static")
)


FILES_DIR = UPLOAD_FOLDERS["Operaciones"]

# Las opciones del formulario y su validación en el servidor salen de los
# catálogos de la base (esquema catalogo): agregar una ruta o una zona no
# requiere tocar código.
def cargar_listas():
    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
        return modelo_catalogos.cargar_listas_del_caso(cursor)


# 🔹 Página principal
@Capturador.route('/')
@login_required
@requiere_permiso('Ingresar_captur_danos')
def index():
    listas = cargar_listas()
    ufs_permitidas = {str(uf) for uf in ufs_autorizadas_sesion()}
    return render_template(
        'Formulario.html',
        listas=listas,
        # Solo las UF de la sesión; el servidor lo vuelve a validar al guardar.
        unidades_funcionales=[uf for uf, _ in listas["unidades_funcionales"] if str(uf) in ufs_permitidas],
        catalogos_formulario=modelo_catalogos.listas_para_el_navegador(listas),
    )

# 🔹 Endpoint de geocodificación
@Capturador.route('/geocode')
@login_required
@requiere_permiso('Ingresar_captur_danos')
def geocode():
    direccion = request.args.get('q', '').strip()
    if not direccion:
        return jsonify([])
    if len(direccion) > 200:
        return jsonify([])
    try:
        url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
        params = {
            "SingleLine": f"{direccion}, Bogotá",
            "f": "json",
            "maxLocations": 5,
            "forStorage": "false"
        }
        # Se valida el certificado TLS. Si la red usa inspección TLS, la CA
        # corporativa se indica con la variable de entorno REQUESTS_CA_BUNDLE.
        res = requests.get(url, params=params, timeout=(3, 10))
        res.raise_for_status()
        data = res.json()
        resultados = []
        for c in data.get("candidates", []):
            resultados.append({
                "nombre": c["address"],
                "lat": c["location"]["y"],
                "lon": c["location"]["x"]
            })
        return jsonify(resultados)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        logger.exception("error_geocodificacion")
        return jsonify([])

# 🔹 Obtener nombre conductor
@Capturador.route('/getConductor')
@login_required
@requiere_permiso('Ingresar_captur_danos')
def get_conductor():
    codigo = request.args.get('codigo', '').strip()
    if not codigo:
        return jsonify({"nombre": None})
    try:
        with sesion_bd(connect) as conn:
            with closing(conn.cursor()) as cursor:
                nombre = modelo_flota.buscar_nombre_del_conductor(cursor, codigo)
        return jsonify({"nombre": nombre})
    except Exception:
        logger.exception("error_consultar_conductor")
        return jsonify({"nombre": None})

# 🔹 Obtener tipología de móvil
@Capturador.route('/getFlota')
@login_required
@requiere_permiso('Ingresar_captur_danos')
def get_flota():
    No_interno = request.args.get('No_interno', '').strip()
    if not No_interno:
        return jsonify({"Tipologia_interno": None, "movil_valido": False})
    ufs = ufs_autorizadas_sesion()
    if not ufs:
        return jsonify({"Tipologia_interno": None, "movil_valido": False})
    try:
        row = consultar_tipologia(No_interno, ufs, connect)
        return jsonify({
            "Tipologia_interno": row[0] if row else None,
            "movil_valido": bool(row)
        })
    except Exception:
        logger.exception("error_consultar_flota")
        return jsonify({"Tipologia_interno": None, "movil_valido": False})


@Capturador.route('/validarDuplicado')
@login_required
@requiere_permiso('Ingresar_captur_danos')
def validar_duplicado():
    fecha = request.args.get("fecha")
    movil = request.args.get("movil")
    codigo = request.args.get("codigo")
    zona_dano = request.args.get("zona_dano")

    try:
        with sesion_bd(connect) as conn:
            with closing(conn.cursor()) as cursor:
                fecha_dt = datetime.strptime(fecha, '%Y-%m-%dT%H:%M')
                existe = modelo_capturador.contar_eventos_iguales(
                    cursor, fecha_dt, movil, codigo, zona_dano) > 0

        return jsonify({"duplicado": existe})

    except Exception:
        logger.exception("error_validar_duplicado")
        return jsonify({"duplicado": False})

@Capturador.route('/submit', methods=['POST'])
@login_required
@requiere_permiso('Ingresar_captur_danos')
def submit_form():
    rutas_guardadas = []
    try:
        # --- 1. PREPARAR LISTA DE ARCHIVOS ---
        # Extraemos todos los archivos de todas las llaves (foto_x, video_x, etc.)
        all_files = []
        for key in request.files:
            for f in request.files.getlist(key):
                if f.filename:
                    all_files.append((key, f))

        for key, f in all_files:
            if f.filename == "blob":
                extension = ".jpg" if "foto" in key.lower() else ".webm"
                f.filename = f"{key}{extension}"
        validate_uploads([f for _, f in all_files])

        # --- 3. DATOS DEL FORMULARIO ---
        # (Tu código de recolección de datos se mantiene igual)
        fecha_evento = request.form.get('Fecha')
        UF = request.form.get('UF')
        if not usuario_puede_acceder_uf(UF):
            return jsonify({"error": "No tiene autorización para registrar en esa UF."}), 403
        Movil = request.form.get('Movil')
        codigo = request.form.get('Codigo')
        nombre = request.form.get('Nombre')
        Area = request.form.get('Area')
        ruta = request.form.get('Ruta')
        tipologia = request.form.get('Tipologia')
        Version_libre = request.form.get('Version_libre')
        parte_afectada = request.form.get('Parte_afectada')
        dano_ocasionado = request.form.get('Dano_ocasionado_por')
        Zona_dano = request.form.get('Zona_dano')
        # El registrador es siempre el usuario de la sesión, nunca el campo del formulario.
        registrador = usuario_id_sesion()
        centro_operaciones = request.form.get('Centro_de_operaciones')
        lat = request.form.get('Latitud')
        lon = request.form.get('Longitud')
        direccion_completa = f"{lat},{lon}" if lat and lon else ""
        fecha_registro = datetime.now()

        campos_requeridos = (
            fecha_evento, UF, Movil, codigo, nombre, Area, ruta, tipologia,
            Version_libre, parte_afectada, dano_ocasionado, Zona_dano,
            centro_operaciones, request.form.get('Direccion'),
        )
        if any(valor is None or not valor.strip() for valor in campos_requeridos):
            return jsonify({"error": "Complete todos los campos obligatorios."}), 400

        parte_afectada = parte_afectada.strip()
        if len(parte_afectada) > 200:
            return jsonify({"error": "La parte afectada no puede superar 200 caracteres."}), 400


        # 1. Obtener la fecha de hoy
        hoy = datetime.today()

        # 2. Definir cuántos días se quieren restar
        dias_a_restar = timedelta(days=62)

        # 3. Restar los días
        fecha_pasada = hoy - dias_a_restar

        try:
            fecha_evento_dt = datetime.strptime(fecha_evento, '%Y-%m-%dT%H:%M')

        except ValueError:
            return jsonify({"error": "Fecha de evento inválida"}), 400

        if not fecha_evento_dt >= fecha_pasada:
            return jsonify({"error": "La fecha ingresada es superior a 2 meses."}), 400

        # El evento no puede ser posterior a su registro (es "ahora"). Los casos
        # que llegaron así eran confusiones de AM/PM o del día cerca de medianoche.
        if fecha_evento_dt > fecha_registro:
            return jsonify({"error": "La fecha del evento no puede ser posterior a la fecha y hora actuales. "
                                     "Revise el día y si la hora es AM o PM."}), 400


        # --- 4. INSERTAR EN DB (REGISTRO PRINCIPAL) ---
        # El helper revierte antes de cerrar y conserva el error para la respuesta.
        with sesion_bd(connect) as conn:
            with closing(conn.cursor()) as cursor:
                listas = modelo_catalogos.cargar_listas_del_caso(cursor)
                error = error_de_catalogo(
                    listas, uf=UF, ruta=ruta, zona_dano=Zona_dano, tipo_dano=dano_ocasionado,
                    centro_operacion=centro_operaciones)
                if error:
                    return jsonify({"error": error}), 400
                if not modelo_flota.movil_pertenece_a_uf(cursor, Movil, UF):
                    return jsonify({"error": "El número de vehículo ingresado no es válido."}), 400

                with transaccion(conn):
                    # La UF y la tipología son las del móvil; el área sale del código.
                    damage_id = modelo_capturador.crear_caso(cursor, {
                        "fecha_evento": fecha_evento_dt, "movil": Movil, "uf": int(UF), "codigo": codigo,
                        "nombre": nombre, "area": area_del_operador(listas, codigo), "ruta": ruta,
                        "direccion": direccion_completa, "version_libre": Version_libre,
                        "parte_afectada": parte_afectada, "dano_ocasionado": dano_ocasionado,
                        "zona_dano": Zona_dano, "registrador": registrador,
                        "centro_operaciones": centro_operaciones, "fecha_registro": fecha_registro,
                    })

                    # --- 5. GUARDADO FÍSICO DE ARCHIVOS ---
                    # Definir rutas
                    damage_folder = FILES_DIR/str(damage_id)
                    damage_folder.mkdir(parents=True, exist_ok=True)

                    for key, f in all_files:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        safe_name = secure_filename(f.filename)
                        final_name = f"{Path(safe_name).stem}_{timestamp}{Path(safe_name).suffix.lower()}"
                        path = store_upload(f, damage_folder, final_name)
                        rutas_guardadas.append(path)

                        modelo_capturador.registrar_adjunto_del_caso(cursor, damage_id, path.name, str(path))


        return jsonify({"mensaje": "Registro exitoso", "id": damage_id})

    except AttachmentValidationError as error:
        for ruta in rutas_guardadas:
            ruta.unlink(missing_ok=True)
        return jsonify({"error": str(error)}), 400
    except Exception:
        for ruta in rutas_guardadas:
            ruta.unlink(missing_ok=True)
        logger.exception("error_guardar_adjuntos_capturador")
        return jsonify({"error": "No fue posible guardar los archivos."}), 500
