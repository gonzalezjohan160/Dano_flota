from conexiones import transaccion
from repositories.flota import consultar_tipologia
from repositories.sesiones import sesion_bd
from contextlib import closing
from pathlib import Path
from flask import Blueprint, request, render_template, jsonify
from datetime import datetime
from config import connect
from werkzeug.utils import secure_filename
from attachment_security import AttachmentValidationError, store_upload, validate_uploads
from logger import logger
from modelos import catalogos as modelo_catalogos
from modelos import flota as modelo_flota
from modelos import reparaciones as modelo_reparaciones
from servicios.montos import leer_valor_monetario
from backend_security import usuario_id_sesion
from backend_security import (
    login_required,
    requiere_permiso,
    usuario_puede_acceder_uf,
    ufs_autorizadas_sesion,
)
from config import BASE_DIR
from config import UPLOAD_FOLDERS


Capturador_rep = Blueprint(
    'Capturador_rep',               # nombre interno del blueprint
    __name__,
    template_folder= str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)


# Ruta donde se guardan los archivos
FILES_DIR = UPLOAD_FOLDERS["Reparaciones"]




# 🔹 Página principal
@Capturador_rep.route('/')
@login_required
@requiere_permiso('Ingresar_captur_reparaciones')
def index():
    # UF y prefijo del móvil salen del catálogo; solo se ofrecen las UF de la sesión.
    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
        unidades = modelo_catalogos.listar_unidades_funcionales(cursor)
    ufs_permitidas = {str(uf) for uf in ufs_autorizadas_sesion()}
    return render_template(
        'Capturador_reparaciones.html',
        unidades_funcionales=[uf for uf, _ in unidades if str(uf) in ufs_permitidas],
        catalogos_formulario={"prefijos_movil": {str(uf): prefijo for uf, prefijo in unidades}},
    )

# 🔹 Obtener tipología de móvil
@Capturador_rep.route('/getFlota')
@login_required
@requiere_permiso('Ingresar_captur_reparaciones')
def get_flota():
    No_interno = request.args.get('No_interno', '').strip()
    if not No_interno:
        return jsonify({"Tipologia_interno": None})
    ufs = ufs_autorizadas_sesion()
    if not ufs:
        return jsonify({"Tipologia_interno": None})
    try:
        row = consultar_tipologia(No_interno, ufs, connect)
        return jsonify({"Tipologia_interno": row[0] if row else None})
    except Exception:
        logger.exception("error_consultar_flota_reparaciones")
        return jsonify({"Tipologia_interno": None})




# 🔹 Recibir formulario y archivos
@Capturador_rep.route('/submit', methods=['POST'])
@login_required
@requiere_permiso('Ingresar_captur_reparaciones')
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

        validate_uploads([f for _, f in all_files])

        # --------------------------------------
        # RECIBIR DATOS NORMALES DEL FORMULARIO
        # --------------------------------------

        Movil = request.form.get('Movil')
        UF = request.form.get('UF')
        if not usuario_puede_acceder_uf(UF):
            return jsonify({"error": "No tiene autorización para registrar en esa UF."}), 403
        Zona_inter = request.form.get('Zona_inter')
        parte_intervenida = request.form.get('Parte_intervenida')
        try:
            costo = leer_valor_monetario(request.form.get('costo'), 'El costo de la reparación')
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        # El registrador es siempre el usuario de la sesión, nunca el campo del formulario.
        registrador = usuario_id_sesion()
        fecha_registro = datetime.now()


        # --------------------------------------
        # CONEXIÓN SQL
        # --------------------------------------
        # El helper revierte antes de cerrar y conserva el error para la respuesta.
        with sesion_bd(connect) as conn:
            with closing(conn.cursor()) as cursor:
                if not modelo_flota.movil_pertenece_a_uf(cursor, Movil, UF):
                    return jsonify({"error": "El móvil no pertenece a la UF seleccionada."}), 400

                with transaccion(conn):
                    repair_id = modelo_reparaciones.crear_reparacion(cursor, {
                        "movil": Movil, "uf": int(UF),
                        "zona_intervenida": Zona_inter, "parte_intervenida": parte_intervenida,
                        "costo": costo, "registrador": registrador, "fecha_registro": fecha_registro,
                    })

                    # --------------------------------------
                    # GUARDADO DE ARCHIVOS
                    # --------------------------------------

                    repair_folder = FILES_DIR / str(repair_id)
                    repair_folder.mkdir(parents=True, exist_ok=True)
                    resolved_repair_folder = repair_folder.resolve()

                    # Iteramos sobre TODOS los archivos enviados en el request.files
                    # No importa si se llaman foto_0, video_1 o adjunto_x
                    for key in request.files:
                        file_list = request.files.getlist(key)

                        for i, f in enumerate(file_list):
                            if not f or f.filename == "":
                                continue

                            # Generar nombre único
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            ext = Path(secure_filename(f.filename)).suffix.lower()

                            # Conservar el prefijo de clasificación, eliminando componentes de ruta.
                            safe_key = secure_filename(key) or "archivo"
                            final_name = secure_filename(f"{safe_key}_{timestamp}_{i}{ext}")
                            path = repair_folder / final_name
                            if path.resolve().parent != resolved_repair_folder:
                                raise AttachmentValidationError("La ruta del archivo no es válida.")

                            # Resetear el puntero por si las validaciones de arriba lo movieron
                            f.seek(0)
                            path = store_upload(f, repair_folder, final_name)
                            rutas_guardadas.append(path)

                            # Guardar en la base de datos
                            modelo_reparaciones.registrar_adjunto_de_reparacion(
                                cursor, repair_id, path.name, str(path))


        return jsonify({"mensaje": "Datos y archivos guardados correctamente"})

    except AttachmentValidationError as error:
        for ruta in rutas_guardadas:
            ruta.unlink(missing_ok=True)
        return jsonify({"error": str(error)}), 400
    except Exception:
        for ruta in rutas_guardadas:
            ruta.unlink(missing_ok=True)
        logger.exception("error_guardar_adjuntos_reparaciones")
        return jsonify({"error": "No fue posible guardar los archivos."}), 500

