from flask import Blueprint, session, render_template, request, jsonify, send_from_directory, send_file, abort
import os
from mimetypes import guess_type
from config import connect
from datetime import datetime
from backend_security import login_required, requiere_permiso

Modulo_mtto = Blueprint(
    'Modulo_mtto',               # nombre interno del blueprint
    __name__,
    template_folder=r'..\frontend',
    static_folder=r'..\Static'
)

UPLOAD_FOLDER = r'C:\media\emapp\dano_flota\Files\Files_mtto'  # carpeta para guardar archivos
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# 🔹 Mostrar la tabla principal
@Modulo_mtto.route('/')
@login_required
@requiere_permiso('Ingresar_modulo__mtto')
def index():

    user_uf = session.get('UF')

    conn = connect()
    cursor = conn.cursor()

# 1. Definimos el fragmento del WHERE y los parámetros
    if user_uf == "Transversal":
        # Aquí ya incluimos los valores directamente
        sql_filter = "d.UF IN (10, 16)"
        params = []
    else:
        # Usamos el marcador de posición estándar
        sql_filter = "d.UF = ?"
        params = [user_uf]

    query_main = f""" 
            SELECT 
                d.Id, d.Fecha_evento, d.Movil, d.Fecha_registro, d.UF, d.Codigo, d.Nombre, d.Ruta,
                d.Tipologia, d.Direccion, d.Version_libre, d.Parte_afectada, d.Dano_ocasionado,
                d.Zona_dano, d.Registrador, d.Centro_operaciones, d.Area,
                (SELECT COUNT(*) FROM table_damage_files f WHERE f.DamageId = d.Id) AS archivos_count
            FROM table_damage_to_fleet d
            WHERE {sql_filter} AND NOT EXISTS (
                SELECT 1
                FROM table_info_mtto m
                WHERE m.Id_damage_to_fleet = d.Id
            )
            ORDER BY d.Id ASC
    """ 
# 3. Ejecución
    try:
        # Ejecutamos pasando params (si está vacío, el driver lo maneja bien)
        cursor.execute(query_main, params)
                
        columns = [column[0] for column in cursor.description] 
        registros = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    except Exception as e:
        print(f"Error en la consulta: {e}")
        registros = []


    for r in registros:
        fecha = r.get('Fecha_evento')
        if fecha is not None:
            r['fecha'] = fecha.strftime("%Y-%m-%d")  # solo fecha
        else:
            r['fecha'] = None
        del r['Fecha_evento']

    # 🔹 Convertir Fecha_registro a string legible para JavaScript
        fecha_r = r.get('Fecha_registro')
        if isinstance(fecha_r, datetime):
            # Formato legible directamente para el usuario
            r['fecha_r'] = fecha_r.strftime("%d/%m/%Y %H:%M:%S")
        elif isinstance(fecha_r, str):
            try:
            # Intentar parsear si viene como string ISO
                fecha_obj_r = datetime.fromisoformat(fecha_r.split('.')[0])
                r['fecha_r'] = fecha_obj_r.strftime("%d/%m/%Y %H:%M:%S")
            except:
                r['fecha_r'] = fecha  # usar tal cual si falla el parseo
        else:
                    r['fecha_r'] = None
        del r['Fecha_registro']


    # 🔹 NUEVO: Traer oper, mtto y svial para cada registro
    for r in registros:
        registro_id = r['Id']
        
        # Operaciones
        cursor.execute("SELECT * FROM table_info_oper WHERE Id_damage_to_fleet = ?", registro_id)
        oper = cursor.fetchall()
        columnas_oper = [col[0] for col in cursor.description]
        r['oper'] = [dict(zip(columnas_oper, row)) for row in oper]  # lista vacía si no hay
        
        
        # Seguridad vial
        cursor.execute("SELECT * FROM table_info_svial WHERE Id_damage_to_fleet = ?", registro_id)
        svial = cursor.fetchall()
        columnas_svial = [col[0] for col in cursor.description]
        r['svial'] = [dict(zip(columnas_svial, row)) for row in svial]

    return render_template("Modulo_mtto.html", registros=registros)

@Modulo_mtto.route('/detalle/<int:id_damage>')
def detalle(id_damage):
    conn = connect()
    cursor = conn.cursor()

    # Traer registro principal
    cursor.execute("SELECT * FROM table_damage_to_fleet WHERE Id = ?", (id_damage,))
    registro_main = cursor.fetchone()
    columnas = [col[0] for col in cursor.description]
    registro = dict(zip(columnas, registro_main)) if registro_main else {}

    # OPERACIONES
    cursor.execute("""
        SELECT Observaciones_operaciones, rev_error, Observaciones_correctivos
        FROM table_info_oper
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    oper = cursor.fetchone()
    if oper:
        oper = dict(zip([col[0] for col in cursor.description], oper))

    # SEGURIDAD VIAL
    cursor.execute("""
        SELECT Observaciones_svial
        FROM table_info_svial
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    svial = cursor.fetchone()
    if svial:
        svial = dict(zip([col[0] for col in cursor.description], svial))

    # ARCHIVOS
    cursor.execute("""
        SELECT DamageId, FileName, FilePath, Fecha_subida
        FROM table_damage_files
        WHERE DamageId = ?
    """, (id_damage,))
    columns_files = [col[0] for col in cursor.description]
    files = [dict(zip(columns_files, row)) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "registro": registro,
        "oper": oper,
        "svial": svial,
        "archivos": files
    })


# 🔹 Ruta de archivos adjuntos
@Modulo_mtto.route("/uploads/<path:filename>")
def uploads(filename):
    """
    Sirve archivos multimedia de manera segura
    """
    safe_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(safe_path):
        return abort(404)
    
    mime_type, _ = guess_type(safe_path)
    return send_file(safe_path, mimetype=mime_type)


# 🔹 Abrir y visualizar archivos adjuntos
@Modulo_mtto.route('/ver_archivo')
def ver_archivo():
    path = request.args.get('path')
    print(f"[DEBUG] Ruta recibida: {path}")

    if not path:
        return abort(400, "Ruta de archivo no especificada")

    # Normaliza la ruta para Windows
    path = os.path.normpath(path)

    if not os.path.exists(path):
        print(f"⚠️ Archivo no encontrado: {path}")
        return abort(404, description="Archivo no encontrado")

    # Detectar tipo MIME según la extensión
    mime_type, _ = guess_type(path)

    try:
        # Si es imagen, video o audio: mostrar directamente en el navegador
        if mime_type and any(t in mime_type for t in ['image', 'video', 'audio']):
            return send_file(path, mimetype=mime_type)
        else:
            # Si es otro tipo (PDF, DOC, ZIP, etc.), ofrecer descarga
            return send_file(path, as_attachment=True)
    except Exception as e:
        print(f"⚠️ Error al enviar archivo: {e}")
        return abort(500, description="Error al abrir el archivo")


os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@Modulo_mtto.route('/agregar_mtto', methods=['POST'])
def agregar_mtto():
    try:
        # Datos del formulario
        codigo = request.form.get('Id_damage_to_fleet')
        costo = request.form.get('Costo')
        usuario = request.form.get('Usuario_registro_mtto')
        Rev_inf = request.form.get('Revinf', 'NO')  # "si" o "no"
        observaciones = request.form.get('observacionesExtra', '')


        if not codigo or not costo or not usuario:
            return jsonify({"status": "error", "message": "Faltan datos obligatorios."})

        # Conectar DB
        conn = connect()
        cursor = conn.cursor()

        # Insertar info de mantenimiento con observaciones y daño adicional
        cursor.execute("""
            INSERT INTO [damage_to_fleet].[dbo].[table_info_mtto]
                (Id_damage_to_fleet, Costo, Usuario_registro_mtto, observaciones, dano_adicional)
            VALUES (?, ?, ?, ?, ?)
        """, (codigo, costo, usuario, observaciones, Rev_inf))
        conn.commit()



        # Carpeta específica por registro
        carpeta_mtto = os.path.join(UPLOAD_FOLDER, str(codigo))
        os.makedirs(carpeta_mtto, exist_ok=True)

        # Procesar archivos
        archivos = request.files.getlist("archivos")
        for archivo in archivos:
            if archivo.filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename_seguro = f"{os.path.splitext(archivo.filename)[0]}_{timestamp}{os.path.splitext(archivo.filename)[1]}"
                ruta_completa = os.path.join(carpeta_mtto, filename_seguro)
                archivo.save(ruta_completa)

                # Guardar en table_mtto_files
                cursor.execute("""
                    INSERT INTO [damage_to_fleet].[dbo].[table_mtto_files]
                        (DamageToFleetId, FileName, FilePath, Fecha_subida)
                    VALUES (?, ?, ?, ?)
                """, (codigo, archivo.filename, ruta_completa, datetime.now()))
        conn.commit()
        conn.close()



        return jsonify({"status": "success", "message": "✅ Mantenimiento y archivos guardados correctamente."})

    except Exception as e:
        print("⚠️ Error al agregar mantenimiento:", e)
        return jsonify({"status": "error", "message": str(e)})



# 🔹 Servir archivos HTML del frontend
@Modulo_mtto.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(r'..', filename)

