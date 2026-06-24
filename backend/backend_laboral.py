from flask import Blueprint, session, render_template, request, jsonify, send_from_directory, send_file, abort
import os
from mimetypes import guess_type
from config import connect
from datetime import datetime
from backend_security import login_required, requiere_permiso

Modulo_laboral = Blueprint(
    'Modulo_laboral',               # nombre interno del blueprint
    __name__,
    template_folder=r'..\frontend',
    static_folder=r'..\Static'
)

UPLOAD_FOLDER = r'C:\media\emapp\dano_flota\Files\Files_laboral'  # carpeta para guardar archivos
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# 🔹 Mostrar la tabla principal
@Modulo_laboral.route('/')
@login_required
@requiere_permiso('Ingresar_modulo__laboral')
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

    # Traemos los registros principales
    query_main = f""" 
            SELECT 
                d.Id, d.Fecha_evento, d.Movil, d.Fecha_registro, d.UF, d.Codigo, d.Nombre, d.Ruta,
                d.Tipologia, d.Direccion, d.Version_libre, d.Parte_afectada, d.Dano_ocasionado,
                d.Zona_dano, d.Registrador, d.Centro_operaciones, d.Area,
                (SELECT COUNT(*) FROM table_damage_files f WHERE f.DamageId = d.Id) AS archivos_count
            FROM table_damage_to_fleet d
            WHERE {sql_filter} AND NOT EXISTS (
                SELECT 1
                FROM table_info_labora m
                WHERE m.Id_damage_to_fleet = d.Id
                AND m.Cerrado = 'SI'
            )
            ORDER BY d.Id ASC
    """ 
    cursor.execute(query_main, params) 
    columns = [column[0] for column in cursor.description] 
    registros = [dict(zip(columns, row)) for row in cursor.fetchall()]


    for r in registros:
        # Fecha evento
        fecha = r.get('Fecha_evento')
        r['fecha'] = fecha.strftime("%Y-%m-%d") if fecha else None
        del r['Fecha_evento']

        # Fecha registro
        fecha_r = r.get('Fecha_registro')
        if isinstance(fecha_r, datetime):
            r['fecha_r'] = fecha_r.strftime("%d/%m/%Y %H:%M:%S")
        elif isinstance(fecha_r, str):
            try:
                fecha_obj_r = datetime.fromisoformat(fecha_r.split('.')[0])
                r['fecha_r'] = fecha_obj_r.strftime("%d/%m/%Y %H:%M:%S")
            except:
                r['fecha_r'] = r['fecha']  # fallback
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
        
        # Mantenimiento
        cursor.execute("SELECT * FROM table_info_mtto WHERE Id_damage_to_fleet = ?", registro_id)
        mtto = cursor.fetchall()
        columnas_mtto = [col[0] for col in cursor.description]
        r['mtto'] = [dict(zip(columnas_mtto, row)) for row in mtto]
        
        # Seguridad vial
        cursor.execute("SELECT * FROM table_info_svial WHERE Id_damage_to_fleet = ?", registro_id)
        svial = cursor.fetchall()
        columnas_svial = [col[0] for col in cursor.description]
        r['svial'] = [dict(zip(columnas_svial, row)) for row in svial]

    return render_template("Modulo_laboral.html", registros=registros)
    # Traemos todos los archivos


@Modulo_laboral.route('/detalle/<int:id_damage>')
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
        SELECT Observaciones_operaciones, rev_error, Observaciones_correctivos, Fecha_registro
        FROM table_info_oper
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    oper = cursor.fetchone()
    if oper:
        oper = dict(zip([col[0] for col in cursor.description], oper))

    # SEGURIDAD VIAL
    cursor.execute("""
        SELECT Observaciones_svial, Fecha_registro
        FROM table_info_svial
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    svial = cursor.fetchone()
    if svial:
        svial = dict(zip([col[0] for col in cursor.description], svial))

    # MANTENIMIENTO
    cursor.execute("""
        SELECT Costo, observaciones, dano_adicional, Fecha_registro
        FROM table_info_mtto
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    mtto = cursor.fetchone()
    if mtto:
        mtto = dict(zip([col[0] for col in cursor.description], mtto))

    # ARCHIVOS
    cursor.execute("""
        SELECT DamageId, FileName, FilePath, Fecha_subida
        FROM table_damage_files
        WHERE DamageId = ?
    """, (id_damage,))
    columns_files = [col[0] for col in cursor.description]
    files = [dict(zip(columns_files, row)) for row in cursor.fetchall()]

        # ARCHIVOS MTTO
    cursor.execute("""
        SELECT DamageToFleetId, FileName, FilePath, Fecha_subida
        FROM table_mtto_files
        WHERE DamageToFleetId = ?
    """, (id_damage,))
    columns_files_mtto = [col[0] for col in cursor.description]
    files_mtto = [dict(zip(columns_files_mtto, row)) for row in cursor.fetchall()]

        # ARCHIVOS S. VIAL
    cursor.execute("""
        SELECT DamageId, FileName, FilePath, Fecha_subida
        FROM table_svial_files
        WHERE DamageId = ?
    """, (id_damage,))
    columns_files_svial = [col[0] for col in cursor.description]
    files_svial = [dict(zip(columns_files_svial, row)) for row in cursor.fetchall()]    

    conn.close()

    return jsonify({
        "registro": registro,
        "oper": oper,
        "svial": svial,
        "mtto": mtto,
        "archivos": files,
        "archivos_mtto": files_mtto,
        "archivos_svial": files_svial        
    })


# 🔹 Abrir y visualizar archivos adjuntos
@Modulo_laboral.route("/uploads/<path:filename>")
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
@Modulo_laboral.route('/ver_archivo')
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

@Modulo_laboral.route('/agregar_laboral', methods=['POST'])
def agregar_laboral():
    try:
        # Datos recibidos
        codigo = request.form.get('Id_damage_to_fleet')
        observaciones_1 = request.form.get('observaciones_1')
        usuario = request.form.get('Usuario_registro_oper')
        Fecha_presentacion = request.form.get('Fecha_presentacion_input')
        Estado_caso = request.form.get('Estado_caso')

        Rev_inf = request.form.get('Revinf', 'NO')
        Cerrado = request.form.get('Cerrado_input', '')
        costo = request.form.get('Costo')

        if not codigo or not observaciones_1 or not usuario:
            return jsonify({"status": "error", "message": "Faltan datos obligatorios."})

        conn = connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO [damage_to_fleet].[dbo].[table_info_laboral_mult]
                (Id_damage_to_fleet, Fecha_presentacion, Pendiente_proceso, Observaciones_rrll, Usuario_registro_laboral, Fecha_registro)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (codigo, Fecha_presentacion, Estado_caso, observaciones_1, usuario, datetime.now()))

        # Lógica para table_info_labora (Validar, Actualizar/Insertar y Auditar)
        if Rev_inf == "SI":
            # Verificar si ya existe un registro para este ID
            cursor.execute("SELECT Tipo_cerrado, Cerrado, Valor_conciliado FROM [table_info_labora] WHERE Id_damage_to_fleet = ?", (codigo,))
            registro_existente = cursor.fetchone()

            if registro_existente:
                # Mapeo de valores para comparar
                campos = {
                    "Tipo_cerrado": (registro_existente[0], Cerrado),
                    "Cerrado": (registro_existente[1], Rev_inf),
                    "Valor_conciliado": (str(registro_existente[2]), str(costo))
                }

                hubo_cambio = False
                for campo, valores in campos.items():
                    valor_anterior, valor_nuevo = valores
                    
                    if str(valor_nuevo) != str(valor_anterior):
                        hubo_cambio = True
                        # Insertar en Auditoría
                        sql_log = """
                            INSERT INTO table_auditoria_correcciones 
                            (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo, Usuario_Modifica, Fecha_Modificacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """
                        cursor.execute(sql_log, (codigo, "table_info_labora", campo, str(valor_anterior), str(valor_nuevo), usuario, datetime.now()))

                if hubo_cambio:
                    # Actualizar el registro existente
                    cursor.execute("""
                        UPDATE [table_info_labora]
                        SET Tipo_cerrado = ?, Cerrado = ?, Valor_conciliado = ?, Usuario_registro_labora = ?
                        WHERE Id_damage_to_fleet = ?
                    """, (Cerrado, Rev_inf, costo, usuario, codigo))
            
            else:
                # Si no existe, insertar normalmente
                cursor.execute("""
                    INSERT INTO [damage_to_fleet].[dbo].[table_info_labora]
                        (Id_damage_to_fleet, Tipo_cerrado, Cerrado, Valor_conciliado, Usuario_registro_labora)
                    VALUES (?, ?, ?, ?, ?)
                """, (codigo, Cerrado, Rev_inf, costo, usuario))

        conn.commit()

        # Carpeta específica por registro
        carpeta_oper = os.path.join(UPLOAD_FOLDER, str(codigo))
        os.makedirs(carpeta_oper, exist_ok=True)

        # Procesar archivos
        archivos = request.files.getlist("archivos")
        for archivo in archivos:
            if archivo.filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename_seguro = f"{os.path.splitext(archivo.filename)[0]}_{timestamp}{os.path.splitext(archivo.filename)[1]}"
                ruta_completa = os.path.join(carpeta_oper, filename_seguro)
                archivo.save(ruta_completa)

                # Guardar en table_laboral_files
                cursor.execute("""
                    INSERT INTO [damage_to_fleet].[dbo].[table_laboral_files]
                        (DamageToFleetId, FileName, FilePath, Fecha_subida)
                    VALUES (?, ?, ?, ?)
                """, (codigo, archivo.filename, ruta_completa, datetime.now()))
        conn.commit()
        conn.close()



        return jsonify({"status": "success", "message": "✅ Información de RRLL y archivos guardados correctamente."})

    except Exception as e:
        print("⚠️ Error al agregar mantenimiento:", e)
        return jsonify({"status": "error", "message": str(e)})



# 🔹 Servir archivos HTML del frontend
@Modulo_laboral.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(r'..', filename)


