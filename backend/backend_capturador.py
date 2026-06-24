import os
from flask import Blueprint, request, session, render_template, jsonify, send_from_directory,send_file, abort
from datetime import datetime
from mimetypes import guess_type
from config import connect
import pyodbc
import requests
import traceback
from backend_security import login_required, requiere_permiso
from backend_email import enviar_correo


Capturador = Blueprint(
    'Capturador',               # nombre interno del blueprint
    __name__,
    template_folder=r'..\frontend',
    static_folder=r'..\Static'
)


FILES_DIR = r'C:\media\emapp\dano_flota\Files\Files_ppal'  # carpeta para guardar archivos
os.makedirs(FILES_DIR, exist_ok=True)



# 🔹 Página principal
@Capturador.route('/')
@login_required
@requiere_permiso('Ingresar_captur_danos')
def index():
    return render_template('Formulario.html')

# 🔹 Archivos estáticos
@Capturador.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(FILES_DIR, filename)

# 🔹 Endpoint de geocodificación
@Capturador.route('/geocode')
def geocode():
    direccion = request.args.get('q', '').strip()
    if not direccion:
        return jsonify([])
    try:
        url = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
        params = {
            "SingleLine": f"{direccion}, Bogotá",
            "f": "json",
            "maxLocations": 5,
            "forStorage": "false"
        }
        res = requests.get(url, params=params, verify=False)
        data = res.json()
        resultados = []
        for c in data.get("candidates", []):
            resultados.append({
                "nombre": c["address"],
                "lat": c["location"]["y"],
                "lon": c["location"]["x"]
            })
        return jsonify(resultados)
    except Exception as e:
        print("Error geocoding:", e)
        return jsonify([])

# 🔹 Obtener nombre conductor
@Capturador.route('/getConductor')
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
        print(traceback.format_exc())
        return jsonify({"nombre": None})

# 🔹 Obtener tipología de móvil
@Capturador.route('/getFlota')
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

@Capturador.route('/validarDuplicado')
def validar_duplicado():
    fecha = request.args.get("fecha")
    movil = request.args.get("movil")
    codigo = request.args.get("codigo")
    zona_dano = request.args.get("zona_dano")

    try:
        conn = connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM table_damage_to_fleet
            WHERE CONVERT(date, Fecha_evento) = CONVERT(date, ?)
            AND Movil = ?
            AND Codigo = ?
            AND Zona_dano = ?
        """, (fecha, movil, codigo, zona_dano))

        existe = cursor.fetchone()[0] > 0
        cursor.close()
        conn.close()

        return jsonify({"duplicado": existe})

    except Exception as e:
        print(e)
        return jsonify({"duplicado": False})      

# --- Definir constantes de restricción ---
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB por archivo
MAX_FILES_COUNT = 5               # Máximo 5 archivos por reporte

@Capturador.route('/submit', methods=['POST'])
def submit_form():
    conn = None # Para asegurar el cierre en caso de error
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

        # --- 3. DATOS DEL FORMULARIO ---
        # (Tu código de recolección de datos se mantiene igual)
        fecha_evento = request.form.get('Fecha')
        UF = request.form.get('UF')
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

        # --- 4. INSERTAR EN DB (REGISTRO PRINCIPAL) ---
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO table_damage_to_fleet 
            (Fecha_evento, UF, Movil, Codigo, Nombre, Area, Ruta, Tipologia, Direccion, 
             Version_libre, Parte_afectada, Dano_ocasionado, Zona_dano, Registrador, 
             Centro_operaciones, Fecha_registro)
            OUTPUT INSERTED.Id 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fecha_evento, UF, Movil, codigo, nombre, Area, ruta, tipologia,
              direccion_completa, Version_libre, parte_afectada, dano_ocasionado,
              Zona_dano, registrador, centro_operaciones, fecha_registro))

        damage_id = cursor.fetchone()[0]

        # --- 5. GUARDADO FÍSICO DE ARCHIVOS ---
        # Definir rutas
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        damage_folder = os.path.join(BASE_DIR, 'Files', 'Files_ppal', str(damage_id))
        os.makedirs(damage_folder, exist_ok=True)

        def allowed_file(filename):
            ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.avi', 
                           '.mov', '.mp3', '.wav', '.pdf', '.ogg', '.webm'}
            return os.path.splitext(filename)[1].lower() in ALLOWED_EXT

        for key, f in all_files:
            filename = f.filename
            
            # Limpiar nombre si viene de Blob de JS
            if not filename or filename.strip() == "" or filename == "blob":
                ext = ".jpg" if "foto" in key else ".webm"
                filename = f"{key}{ext}"

            if allowed_file(filename):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name, ext = os.path.splitext(filename)
                final_name = f"{name}_{timestamp}{ext}"
                path = os.path.join(damage_folder, final_name)
                
                # Guardar en disco
                f.save(path)

                # Registrar en tabla de archivos
                cursor.execute("""
                    INSERT INTO table_damage_files (DamageId, FileName, FilePath)
                    VALUES (?, ?, ?)
                """, (damage_id, final_name, path))
                
        conn.commit()
        
        mensaje = f"""
                    <h2>Nuevo Evento Registrado</h2>
                    
                    <p>Se ha registrado un nuevo daño a Flota en el sistema.</p>

                    <p><b>ID Caso:</b> {damage_id}</p>

                    <p>Por favor ingresar al aplicativo para revisar la información.</p>

                <hr>

                """
        
        # consultar correos
        cursor.execute(
        """
            SELECT Email
            FROM Table_usuarios
            WHERE Activo = 1
            AND Email IS NOT NULL
            AND Email <> ''
        """)
            
        destinatarios = [row[0] for row in cursor.fetchall()]
        
        print("Destinatarios:", destinatarios)
        
        try:
            if destinatarios:
                enviar_correo(destinatarios, "Nuevo Evento Registrado", mensaje)
        except Exception as email_error:
            print(f"Error al enviar correo: {email_error}")
        
        return jsonify({"mensaje": "Registro exitoso", "id": damage_id})
    
    

    except Exception as e:
        if conn: conn.rollback()
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        if conn: conn.close()
