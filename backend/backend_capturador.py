import os
from flask import Blueprint, request, session, render_template, jsonify, send_file, abort
from datetime import datetime, date, timedelta
from mimetypes import guess_type
from config import connect
import pyodbc
import requests
import traceback
from backend_security import (
    login_required,
    requiere_permiso,
    usuario_puede_acceder_uf,
    ufs_autorizadas_sesion,
)
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask
from config import BASE_DIR
from config import UPLOAD_FOLDERS
from attachment_security import (
    AttachmentValidationError,
    store_upload,
    validate_uploads,
)
from logger import logger
from backend_historico_movil import parse_fecha


Capturador = Blueprint(
    "Capturador",                                   # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR / "frontend"),
    static_folder=str(BASE_DIR / "Static")               
)


FILES_DIR = UPLOAD_FOLDERS["Operaciones"]

# Fuente única para las opciones del formulario y su validación en servidor.
ZONAS_DANO = (
    "LATERAL IZQUIERDO", "LATERAL DERECHO", "FRONTAL", "POSTERIOR",
    "TECHO", "ESPEJOS", "PUERTAS", "VIDRIOS", "LLANTAS", "ITS",
    "SIRCI", "CARROCERÍA INTERNA", "TREN MOTRIZ", "CHASIS",
)
DANOS_OCASIONADOS_POR = (
    "CONDUCTA OPERACIONAL", "INFRAESTRUCTURA PATIO", "INFRAESTRUCTURA VIAL",
    "VANDALISMO", "MECÁNICO", "SINIESTRO VIAL", "ALISTAMIENTO",
)


FILES_DIR.mkdir(parents=True, exist_ok=True)



# 🔹 Página principal
@Capturador.route('/')
@login_required
@requiere_permiso('Ingresar_captur_danos')
def index():
    return render_template(
        'Formulario.html',
        zonas_dano=ZONAS_DANO,
        danos_ocasionados_por=DANOS_OCASIONADOS_POR,
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
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("SELECT Nombre_OBZ FROM table_drivers WHERE Codigo_OBZ = ?", (codigo,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({"nombre": row[0] if row else None})
    except Exception:
        
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
        conn = connect()
        cursor = conn.cursor()
        marcadores = ", ".join("?" for _ in ufs)
        cursor.execute(
            f"SELECT Tipologia_Movil FROM table_Moviles WHERE No_Movil = ? AND UF IN ({marcadores})",
            (No_interno, *ufs),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({
            "Tipologia_interno": row[0] if row else None,
            "movil_valido": bool(row)
        })
    except Exception:
        
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
        conn = connect()
        cursor = conn.cursor()
        fecha_dt = datetime.strptime(fecha, '%Y-%m-%dT%H:%M')  

        cursor.execute("""
            SELECT COUNT(*)
            FROM table_damage_to_fleet
            WHERE CONVERT(date, Fecha_evento) = CONVERT(date, ?)
            AND Movil = ?
            AND Codigo = ?
            AND Zona_dano = ?
        """, (fecha_dt, movil, codigo, zona_dano))

        existe = cursor.fetchone()[0] > 0
        cursor.close()
        conn.close()

        return jsonify({"duplicado": existe})

    except Exception as e:
        return jsonify({"duplicado": False})      

# --- Definir constantes de restricción ---
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB por archivo
MAX_FILES_COUNT = 5               # Máximo 5 archivos por reporte

@Capturador.route('/submit', methods=['POST'])
@login_required
@requiere_permiso('Ingresar_captur_danos')
def submit_form():
    conn = None # Para asegurar el cierre en caso de error
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

        # --- 2. VALIDACIONES ---
        if len(all_files) > MAX_FILES_COUNT:
            return jsonify({"error": f"Máximo {MAX_FILES_COUNT} archivos permitidos."}), 400

        for key, f in all_files:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(0) # IMPORTANTE: Volver al inicio para poder guardarlo después
            if size > MAX_FILE_SIZE:
                return jsonify({"error": f"El archivo {f.filename} es muy pesado."}), 400

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
        registrador = request.form.get('Inspector')
        centro_operaciones = request.form.get('Centro_de_operaciones')
        lat = request.form.get('Latitud')
        lon = request.form.get('Longitud')
        direccion_completa = f"{lat},{lon}" if lat and lon else ""
        fecha_registro = datetime.now()

        campos_requeridos = (
            fecha_evento, UF, Movil, codigo, nombre, Area, ruta, tipologia,
            Version_libre, parte_afectada, dano_ocasionado, Zona_dano,
            registrador, centro_operaciones, request.form.get('Direccion'),
        )
        if any(valor is None or not valor.strip() for valor in campos_requeridos):
            return jsonify({"error": "Complete todos los campos obligatorios."}), 400

        if Zona_dano not in ZONAS_DANO:
            return jsonify({"error": "La zona del daño no es válida."}), 400

        if dano_ocasionado not in DANOS_OCASIONADOS_POR:
            return jsonify({"error": "La causa del daño no es válida."}), 400

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
            

        # --- 4. INSERTAR EN DB (REGISTRO PRINCIPAL) ---
        conn = connect()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM table_Moviles WHERE No_Movil = ? AND UF = ?", (Movil, UF))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "El número de vehículo ingresado no es válido."}), 400

        cursor.execute("""
            INSERT INTO table_damage_to_fleet 
            (Fecha_evento, UF, Movil, Codigo, Nombre, Area, Ruta, Tipologia, Direccion, 
             Version_libre, Parte_afectada, Dano_ocasionado, Zona_dano, Registrador, 
             Centro_operaciones, Fecha_registro)
            OUTPUT INSERTED.Id 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fecha_evento_dt, UF, Movil, codigo, nombre, Area, ruta, tipologia,
              direccion_completa, Version_libre, parte_afectada, dano_ocasionado,
              Zona_dano, registrador, centro_operaciones, fecha_registro))

        damage_id = cursor.fetchone()[0]

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

            cursor.execute("""
                INSERT INTO table_damage_files (DamageId, FileName, FilePath)
                VALUES (?, ?, ?)
            """, (damage_id, path.name, str(path)))
                
        conn.commit()
             
        
        return jsonify({"mensaje": "Registro exitoso", "id": damage_id})
    
    except AttachmentValidationError as error:
        if conn:
            conn.rollback()
        for ruta in rutas_guardadas:
            ruta.unlink(missing_ok=True)
        return jsonify({"error": str(error)}), 400
    except Exception:
        if conn: conn.rollback()
        for ruta in rutas_guardadas:
            ruta.unlink(missing_ok=True)
        logger.exception("error_guardar_adjuntos_capturador")
        return jsonify({"error": "No fue posible guardar los archivos."}), 500
    finally:
        if conn: conn.close()
