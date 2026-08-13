from flask import Blueprint, render_template, request, jsonify, session, send_from_directory, send_file, abort
import os
from mimetypes import guess_type
from config import connect
from datetime import datetime, timedelta
from backend_security import login_required, requiere_permiso
from config import BASE_DIR
from config import UPLOAD_FOLDERS

Correcciones = Blueprint(
    'Correcciones',               # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)


# 🔹 Vista principal (HTML)
@Correcciones.route('/')
@login_required
@requiere_permiso('Ingresar_correcciones')
def index():
    # Puedes pasar inicialmente registros vacíos
    registros = []  
    return render_template("Front_correcciones.html", registros=registros)

# Endpoint para obtener todos los datos de un registro por ID
@Correcciones.route('/detalle/<int:id_damage>')
@login_required
def detalle(id_damage):
    conn = connect()
    cursor = conn.cursor()

    # 🔹 Registro principal
    cursor.execute("SELECT * FROM table_damage_to_fleet WHERE Id = ?", (id_damage,))
    registro_main = cursor.fetchone()
    columnas = [col[0] for col in cursor.description]
    registro = dict(zip(columnas, registro_main)) if registro_main else {}

    # 🔹 Operaciones
    cursor.execute("""
        SELECT Observaciones_operaciones, rev_error, Observaciones_correctivos, Fecha_registro, Usuario_registro_oper
        FROM table_info_oper
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    oper = cursor.fetchone()
    oper = dict(zip([col[0] for col in cursor.description], oper)) if oper else {}

    # 🔹 Seguridad vial
    cursor.execute("""
        SELECT Observaciones_svial, Fecha_registro, Usuario_registro_svial
        FROM table_info_svial
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    svial = cursor.fetchone()
    svial = dict(zip([col[0] for col in cursor.description], svial)) if svial else {}

    # 🔹 Mantenimiento
    cursor.execute("""
        SELECT Costo, observaciones, dano_adicional, Fecha_registro, Usuario_registro_mtto
        FROM table_info_mtto
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    mtto = cursor.fetchone()
    mtto = dict(zip([col[0] for col in cursor.description], mtto)) if mtto else {}

    # 🔹 Laboral único
    cursor.execute("""
        SELECT Tipo_cerrado, Valor_conciliado, Fecha_registro, Usuario_registro_labora
        FROM table_info_labora
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    laboral = cursor.fetchone()
    laboral = dict(zip([col[0] for col in cursor.description], laboral)) if laboral else {}

    # 🔹 Laboral múltiple
    cursor.execute("""
        SELECT Fecha_presentacion, Pendiente_proceso, Observaciones_rrll, Fecha_registro, Usuario_registro_laboral
        FROM table_info_laboral_mult
        WHERE Id_damage_to_fleet = ?
    """, (id_damage,))
    columnas_laboralm = [col[0] for col in cursor.description]
    laboralm = [dict(zip(columnas_laboralm, row)) for row in cursor.fetchall()]

    # 🔹 Archivos principales
    cursor.execute("""
        SELECT DamageId, FileName, FilePath, Fecha_subida
        FROM table_damage_files
        WHERE DamageId = ?
    """, (id_damage,))
    columns_files = [col[0] for col in cursor.description]
    files = [dict(zip(columns_files, row)) for row in cursor.fetchall()]

    # 🔹 Archivos laboral
    cursor.execute("""
        SELECT DamageToFleetId, FileName, FilePath, Fecha_subida
        FROM table_laboral_files
        WHERE DamageToFleetId = ?
    """, (id_damage,))
    columns_files_laboral = [col[0] for col in cursor.description]
    files_laboral = [dict(zip(columns_files_laboral, row)) for row in cursor.fetchall()]

    # 🔹 Archivos mantenimiento
    cursor.execute("""
        SELECT DamageToFleetId, FileName, FilePath, Fecha_subida
        FROM table_mtto_files
        WHERE DamageToFleetId = ?
    """, (id_damage,))
    columns_files_mtto = [col[0] for col in cursor.description]
    files_mtto = [dict(zip(columns_files_mtto, row)) for row in cursor.fetchall()]

    # 🔹 Archivos seguridad vial
    cursor.execute("""
        SELECT DamageId, FileName, FilePath, Fecha_subida
        FROM table_svial_files
        WHERE DamageId = ?
    """, (id_damage,))
    columns_files_svial = [col[0] for col in cursor.description]
    files_svial = [dict(zip(columns_files_svial, row)) for row in cursor.fetchall()]

    conn.close()

    # 🔹 Respuesta JSON que usa el JS
    return jsonify({
        "registro": registro,
        "oper": oper,
        "svial": svial,
        "mtto": mtto,
        "laboral": laboral,
        "laboralm": laboralm,
        "archivos": files,
        "archivos_laboral": files_laboral,
        "archivos_mtto": files_mtto,
        "archivos_svial": files_svial
    })

# --- CONFIGURACIÓN DE RUTAS POR ÁREA ---
PATHS = {
    "oper": UPLOAD_FOLDERS["Operaciones"],
    "mtto": UPLOAD_FOLDERS["Mtto"],
    "svial": UPLOAD_FOLDERS["Svial"],
    "laboral": UPLOAD_FOLDERS["laboral"]
}

# Recorremos el diccionario y creamos cada carpeta si no existe
for area, ruta in PATHS.items():
    ruta.mkdir(parents=True, exist_ok=True)
        

def procesar_archivos_area(request_files, key, folder_base, table_name, id_damage, cursor):
    """
    Función optimizada para el guardado de archivos y registro en DB
    """
    if key in request_files:
        archivos = request_files.getlist(key)
        # Carpeta específica por ID de daño
        ruta_area = folder_base / str(id_damage)
        ruta_area.mkdir(parents=True, exist_ok=True)

        for archivo in archivos:
            if archivo.filename != '':
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name, ext = os.path.splitext(archivo.filename)
                nombre_final = f"{name}_{timestamp}{ext}"
                ruta_fisica = ruta_area / nombre_final
                
                archivo.save(str(ruta_fisica))

                # Selección dinámica de columna de ID según tu esquema
                col_id = "DamageId" if table_name in ["table_damage_files", "table_svial_files"] else "DamageToFleetId"

                sql = f"""
                    INSERT INTO [damage_to_fleet].[dbo].[{table_name}]
                    ({col_id}, FileName, FilePath, Fecha_subida)
                    VALUES (?, ?, ?, ?)
                """
                cursor.execute(sql, (id_damage, archivo.filename, str(ruta_fisica), datetime.now()))

@Correcciones.route('/modificar/<int:id_damage>', methods=['POST'])
@login_required
def modificar(id_damage):

    print(f"--- INICIANDO ACTUALIZACIÓN ID: {id_damage} ---")
    print("Archivos recibidos en request.files:", request.files.keys())
    print("Datos recibidos en request.form:", request.form.to_dict())

    # Usamos request.form porque FormData envía datos multipart
    data = request.form 
    usuario_actual = data.get('Usuario_registro_mtto', 'Usuario_Desconocido')
    
    tablas_mapeo = {
        "table_damage_to_fleet": ["Fecha_evento", "Movil", "Codigo", "Nombre", "Area", "Ruta", "Version_libre", "Zona_dano", "Parte_afectada", "Dano_ocasionado", "Centro_operaciones", "Direccion"],
        "table_info_oper": ["Observaciones_operaciones", "rev_error", "Observaciones_correctivos"],
        "table_info_mtto": ["Costo", "dano_adicional", "Observaciones_mtto"],
        "table_info_svial": ["Observaciones_svial"],
        "table_info_labora": ["Valor_conciliado", "Tipo_cerrado"]
    }

    conn = connect()
    cursor = conn.cursor()

    try:
        # --- 1. PROCESAR CAMBIOS DE TEXTO Y AUDITORÍA ---
        for tabla, campos in tablas_mapeo.items():
            updates = {k: v for k, v in data.items() if k in campos}
            
            if updates:
                # Normalización de nombre de campo para Mantenimiento
                if "Observaciones_mtto" in updates:
                    updates["observaciones"] = updates.pop("Observaciones_mtto")

                pk_col = "Id" if tabla == "table_damage_to_fleet" else "Id_damage_to_fleet"

                for campo, nuevo_valor in updates.items():
                    # Obtener valor actual para comparar
                    cursor.execute(f"SELECT {campo} FROM {tabla} WHERE {pk_col} = ?", (id_damage,))
                    row = cursor.fetchone()
                    
                    valor_anterior_raw = row[0] if row else ""
                    valor_anterior = str(valor_anterior_raw).strip() if valor_anterior_raw is not None else ""
                    nuevo_valor_str = str(nuevo_valor).strip()

                    # Solo auditar si hubo cambio real
                    if nuevo_valor_str != valor_anterior:
                        sql_log = """
                            INSERT INTO table_auditoria_correcciones 
                            (Id_damage, Tabla_Afectada, Campo_Modificado, Valor_Anterior, Valor_Nuevo, Usuario_Modifica, Fecha_Modificacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """
                        cursor.execute(sql_log, (id_damage, tabla, campo, valor_anterior, nuevo_valor_str, usuario_actual, datetime.now()))

                # Ejecutar actualización masiva de la tabla
                set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
                valores = list(updates.values())
                valores.append(id_damage)
                cursor.execute(f"UPDATE {tabla} SET {set_clause} WHERE {pk_col} = ?", tuple(valores))

        # --- 2. PROCESAR ARCHIVOS POR ÁREA ---
        # Llamadas a la función auxiliar con las carpetas y tablas correspondientes
        procesar_archivos_area(request.files, 'archivos_oper', PATHS['oper'], 'table_damage_files', id_damage, cursor)
        procesar_archivos_area(request.files, 'archivos_mtto', PATHS['mtto'], 'table_mtto_files', id_damage, cursor)
        procesar_archivos_area(request.files, 'archivos_svial', PATHS['svial'], 'table_svial_files', id_damage, cursor)
        procesar_archivos_area(request.files, 'archivos_laboral', PATHS['laboral'], 'table_laboral_files', id_damage, cursor)

        conn.commit()
        return jsonify({"success": True, "message": "Datos actualizados, auditoría generada y archivos organizados por área."})

    except Exception as e:
        if conn: conn.rollback()
        print(f"ERROR CRÍTICO: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    finally:
        if conn: conn.close()
