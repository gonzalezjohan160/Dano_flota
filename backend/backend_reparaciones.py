import os
from pathlib import Path
from flask import Blueprint, request, render_template, session, jsonify, send_file, abort
from datetime import datetime
from mimetypes import guess_type
from config import connect
from werkzeug.utils import secure_filename
from attachment_security import AttachmentValidationError, store_upload, validate_uploads
from logger import logger
import traceback
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

# Crear la carpeta si no existe
FILES_DIR.mkdir(parents=True, exist_ok=True)



# 🔹 Página principal
@Capturador_rep.route('/')
@login_required
@requiere_permiso('Ingresar_captur_reparaciones')
def index():
    return render_template('Capturador_reparaciones.html')

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
        return jsonify({"Tipologia_interno": row[0] if row else None})
    except Exception:
    
        return jsonify({"Tipologia_interno": None})

      

# --- Definir constantes de restricción ---
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB por archivo
MAX_FILES_COUNT = 5               # Máximo 5 archivos por reporte        
  

# 🔹 Recibir formulario y archivos
@Capturador_rep.route('/submit', methods=['POST'])
@login_required
@requiere_permiso('Ingresar_captur_reparaciones')
def submit_form():
    rutas_guardadas = []
    conn = None

    try:

                # --- 1. PREPARAR LISTA DE ARCHIVOS ---
        # Extraemos todos los archivos de todas las llaves (foto_x, video_x, etc.)
        all_files = []
        for key in request.files:
            for f in request.files.getlist(key):
                if f.filename:
                    all_files.append((key, f))

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

        # --------------------------------------
        # RECIBIR DATOS NORMALES DEL FORMULARIO
        # --------------------------------------

        Movil = request.form.get('Movil')
        UF = request.form.get('UF')
        if not usuario_puede_acceder_uf(UF):
            return jsonify({"error": "No tiene autorización para registrar en esa UF."}), 403
        tipologia = request.form.get('Tipologia')
        Zona_inter = request.form.get('Zona_inter')
        parte_intervenida = request.form.get('Parte_intervenida')
        costo = request.form.get('costo')
        registrador = request.form.get('Usuario')
        fecha_registro = datetime.now()


        # --------------------------------------
        # CONEXIÓN SQL
        # --------------------------------------
        conn = connect()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM table_Moviles WHERE No_Movil = ? AND UF = ?",
            (Movil, UF),
        )
        if not cursor.fetchone():
            conn.close()
            conn = None
            return jsonify({"error": "El móvil no pertenece a la UF seleccionada."}), 400

        cursor.execute("""
            INSERT INTO table_intervenciones 
            (Movil, UF, Tipologia, Zona_intervenida, Parte_intervenida, Costo_intervencion, Usuario_registro, 
             Fecha_registro)
            OUTPUT INSERTED.Id 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            Movil, UF, tipologia, Zona_inter, parte_intervenida, costo, registrador, fecha_registro 
        ))

        repair_id = cursor.fetchone()[0]

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
                cursor.execute("""
                    INSERT INTO table_intervenciones_files
                    (RepairId, FileName, FilePath)
                    VALUES (?, ?, ?)
                """, (repair_id, path.name, str(path)))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"mensaje": "Datos y archivos guardados correctamente"})

    except AttachmentValidationError as error:
        for ruta in rutas_guardadas:
            ruta.unlink(missing_ok=True)
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({"error": str(error)}), 400
    except Exception:
        for ruta in rutas_guardadas:
            ruta.unlink(missing_ok=True)
        if conn:
            conn.rollback()
            conn.close()
        logger.exception("error_guardar_adjuntos_reparaciones")
        return jsonify({"error": "No fue posible guardar los archivos."}), 500

