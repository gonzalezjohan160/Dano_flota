import os
from pathlib import Path
from flask import Blueprint, request, render_template, session, jsonify, send_file, abort
from datetime import datetime
from mimetypes import guess_type
from config import connect
from werkzeug.utils import secure_filename
import traceback
from backend_security import login_required, requiere_permiso
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
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("SELECT Tipologia_Movil FROM table_Moviles WHERE No_Movil = ?", (No_interno,))
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

    try:

                # --- 1. PREPARAR LISTA DE ARCHIVOS ---
        # Extraemos todos los archivos de todas las llaves (foto_x, video_x, etc.)
        all_files = []
        for key in request.files:
            for f in request.files.getlist(key):
                if f.filename:
                    all_files.append((key, f))

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
        conn.commit()

        # --------------------------------------
        # GUARDADO DE ARCHIVOS
        # --------------------------------------
      
        repair_folder = FILES_DIR / str(repair_id)
        repair_folder.mkdir(parents=True, exist_ok=True)
        resolved_repair_folder = repair_folder.resolve()

        def allowed_file(filename):
                    ext = os.path.splitext(filename)[1].lower()
                    ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', 
                                '.mov', '.mp3', '.wav', '.pdf', '.ogg', '.webm','.opus'}
                    return ext in ALLOWED_EXT

        # Iteramos sobre TODOS los archivos enviados en el request.files
        # No importa si se llaman foto_0, video_1 o adjunto_x
        for key in request.files:
            file_list = request.files.getlist(key)
            
            for i, f in enumerate(file_list):
                if not f or f.filename == "":
                    continue

                if not allowed_file(f.filename):
                
                    continue

                # Generar nombre único
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                _, ext = os.path.splitext(f.filename)

                # Conservar el prefijo de clasificación, eliminando componentes de ruta.
                safe_key = secure_filename(key) or "archivo"
                final_name = f"{safe_key}_{timestamp}_{i}{ext}"
                path = repair_folder / final_name
                if path.resolve().parent != resolved_repair_folder:
                    raise ValueError("La ruta del archivo debe permanecer en la carpeta de reparación")

                # Resetear el puntero por si las validaciones de arriba lo movieron
                f.seek(0)
                f.save(str(path))

                # Guardar en la base de datos
                cursor.execute("""
                    INSERT INTO table_intervenciones_files
                    (RepairId, FileName, FilePath)
                    VALUES (?, ?, ?)
                """, (repair_id, final_name, str(path)))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"mensaje": "Datos y archivos guardados correctamente"})

    except Exception as e:
        
        return jsonify({"error": str(e)}), 500

