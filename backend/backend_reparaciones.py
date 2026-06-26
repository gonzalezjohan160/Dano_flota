import os
from flask import Blueprint, request, render_template, session, jsonify, send_from_directory,send_file, abort
from datetime import datetime
from mimetypes import guess_type
from config import connect
import traceback
from backend_security import login_required, requiere_permiso

Capturador_rep = Blueprint(
    'Capturador_rep',               # nombre interno del blueprint
    __name__,
    template_folder=r'..\frontend',
    static_folder=r'..\Static'
)

# Ruta donde se guardan los archivos
FILES_DIR = r'C:\media\emapp\dano_flota\Files\Files_reparaciones'  # carpeta para guardar archivos
os.makedirs(FILES_DIR, exist_ok=True)



# 🔹 Página principal
@Capturador_rep.route('/')
@login_required
@requiere_permiso('Ingresar_captur_reparaciones')
def index():
    return render_template('Capturador_reparaciones.html')

# 🔹 Archivos estáticos
@Capturador_rep.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(FILES_DIR, filename)


# 🔹 Obtener tipología de móvil
@Capturador_rep.route('/getFlota')
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
        print(traceback.format_exc())
        return jsonify({"Tipologia_interno": None})

      

# --- Definir constantes de restricción ---
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB por archivo
MAX_FILES_COUNT = 5               # Máximo 5 archivos por reporte        
  

# 🔹 Recibir formulario y archivos
@Capturador_rep.route('/submit', methods=['POST'])
def submit_form():

    print("====== DEBUG REQUEST ======")
    print("Content-Type:", request.content_type)
    print("Form keys:", list(request.form.keys()))
    print("Files keys:", list(request.files.keys()))
    print("Raw files:", request.files)
    print("===========================")


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
      
        repair_folder = os.path.join(FILES_DIR, str(repair_id))
        os.makedirs(repair_folder, exist_ok=True)

        def allowed_file(filename):
                    ext = os.path.splitext(filename)[1].lower()
                    ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', 
                                '.mov', '.mp3', '.wav', '.pdf', '.ogg', '.webm'}
                    return ext in ALLOWED_EXT

        # Iteramos sobre TODOS los archivos enviados en el request.files
        # No importa si se llaman foto_0, video_1 o adjunto_x
        for key in request.files:
            file_list = request.files.getlist(key)
            
            for i, f in enumerate(file_list):
                if not f or f.filename == "":
                    continue

                if not allowed_file(f.filename):
                    print(f"Archivo no permitido: {f.filename}")
                    continue

                # Generar nombre único
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                _, ext = os.path.splitext(f.filename)
                
                # El nombre final usará la 'key' original (foto, video, etc) para saber qué es
                final_name = f"{key}_{timestamp}_{i}{ext}"
                path = os.path.join(repair_folder, final_name)

                # Resetear el puntero por si las validaciones de arriba lo movieron
                f.seek(0)
                f.save(path)

                # Guardar en la base de datos
                cursor.execute("""
                    INSERT INTO table_intervenciones_files
                    (RepairId, FileName, FilePath)
                    VALUES (?, ?, ?)
                """, (repair_id, final_name, path))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"mensaje": "Datos y archivos guardados correctamente"})

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

