from flask import Blueprint, render_template, request, jsonify, send_from_directory, send_file, abort
import os
from mimetypes import guess_type
from config import connect
from datetime import datetime
from backend_security import login_required, requiere_permiso
from config import BASE_DIR
from config import UPLOAD_FOLDERS
from pathlib import Path

Historico_movil = Blueprint(
    'Historico_movil',               # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)


# 🔹 Mostrar la tabla principal
@Historico_movil.route('/')
@login_required
@requiere_permiso('Ingresar_danos_vs_reparaciones')
def index():
    # Capturamos el número del móvil desde la consulta (query string)
    movil_filtro = request.args.get('movil', '').strip()

    registros = []
    if movil_filtro:

        conn = connect()
        cursor = conn.cursor()

            
        # Traemos los registros principales
        query_union = """
            SELECT
                d.Id as id,
                d.Fecha_evento as fecha,
                d.Movil,
                (
                    SELECT SUM(i.Costo)
                    FROM table_info_mtto i
                    WHERE i.Id_damage_to_fleet = d.Id
                ) as costo,
                'DAÑO' as tipo,
                (SELECT COUNT(*) 
                FROM table_damage_files f 
                WHERE f.DamageId = d.Id) AS archivos_count
            FROM table_damage_to_fleet d
            WHERE d.Movil = ?

            UNION ALL

            SELECT
                p.Id as id,
                p.Fecha_registro as fecha,
                p.Movil,
                p.Costo_intervencion as costo,
                'REPARACIÓN' as tipo,
                (SELECT COUNT(*) 
                FROM table_intervenciones_files k 
                WHERE k.RepairId = p.Id) AS archivos_count
            FROM table_intervenciones p
            WHERE p.Movil = ?

            ORDER BY fecha DESC
        """
        cursor.execute(query_union, (movil_filtro, movil_filtro))
        columns = [col[0] for col in cursor.description]
        registros = [dict(zip(columns, row)) for row in cursor.fetchall()]

    

    # 🔹 NUEVO: Traer oper, mtto y svial para cada registro
    for r in registros:
        registro_id = r['id']
        
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

    return render_template("Front_historico_movil.html", registros=registros)
    # Traemos todos los archivos


@Historico_movil.route('/detalle/<int:id_damage>')
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

    conn.close()

    return jsonify({
        "registro": registro,
        "oper": oper,
        "svial": svial,
        "mtto": mtto,
        "archivos": files
    })

@Historico_movil.route('/detalle_reparacion/<int:id>')
def detalle_reparacion(id):
    conn = connect()
    cursor = conn.cursor()

    # Registro principal de la reparación
    cursor.execute("""
        SELECT *
        FROM table_intervenciones
        WHERE Id = ?
    """, (id,))
    registro_main = cursor.fetchone()
    columnas = [col[0] for col in cursor.description]
    registro = dict(zip(columnas, registro_main)) if registro_main else {}

    # ARCHIVOS REPARACIONES
    cursor.execute("""
        SELECT RepairId, FileName, FilePath, Fecha_subida
        FROM table_intervenciones_files
        WHERE RepairId = ?
    """, (id,))
    columns_files = [col[0] for col in cursor.description]
    files = [dict(zip(columns_files, row)) for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "registro": registro,
        "archivos": files
    })


# 🔹 Abrir y visualizar archivos adjuntos
@Historico_movil.route('/ver_archivo')
def ver_archivo():
    path = request.args.get('path')
    print(f"[DEBUG] Ruta recibida: {path}")

    if not path:
        return abort(400, "Ruta de archivo no especificada")

    # Convertir a Path
    path = Path(path).resolve()
    
    # Verificar que el archivo pertenezca a una carpeta permitida
    permitido = any(
        carpeta.resolve() in path.parents
        for carpeta in UPLOAD_FOLDERS.values()
    )

    if not permitido:
        abort(403)
        
    if not path.is_file():
        print(f"⚠️ Archivo no encontrado: {path}")
        abort(404, description="Archivo no encontrado")    

    # Detectar tipo MIME según la extensión
    mime_type, _ = guess_type(str(path))

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




# 🔹 Servir archivos HTML del frontend
@Historico_movil.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(r'..', filename)


