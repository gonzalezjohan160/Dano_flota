from flask import Blueprint, render_template, request, jsonify, send_from_directory, send_file, abort
import os
import math
import io
from mimetypes import guess_type
from config import connect
from datetime import datetime, timedelta
from backend_security import login_required, requiere_permiso
from config import BASE_DIR
from config import UPLOAD_FOLDERS
from pathlib import Path
from openpyxl import Workbook

Historico_movil = Blueprint(
    'Historico_movil',               # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)

REGISTROS_POR_PAGINA = 30


def _leer_filtros():
    """Lee y normaliza los filtros de Histórico Móvil desde la query string."""
    movil = request.args.get('movil', '').strip()
    tipo = request.args.get('tipo', 'todos').strip().lower()
    if tipo not in ('todos', 'danos', 'reparaciones'):
        tipo = 'todos'
    uf = request.args.get('uf', 'todos').strip().lower()
    if uf not in ('todos', '10', '16'):
        uf = 'todos'
    fecha_inicio = request.args.get('fecha_inicio', '').strip()
    fecha_fin = request.args.get('fecha_fin', '').strip()

    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except (TypeError, ValueError):
        page = 1

    return {
        'movil': movil,
        'tipo': tipo,
        'uf': uf,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'page': page,
    }


def _subquery_danos(filtros):
    """Arma el SELECT de daños con sus filtros. Devuelve (sql, params)."""

    sql = """
    SELECT
        d.Id AS id,
        d.Fecha_evento AS fecha,
        d.Movil,
        d.UF AS UF,
        (
            SELECT SUM(i.Costo)
            FROM table_info_mtto i
            WHERE i.Id_damage_to_fleet = d.Id
        ) AS costo,
        'DAÑO' AS tipo,
        (
            SELECT COUNT(*)
            FROM table_damage_files f
            WHERE f.DamageId = d.Id
        ) AS archivos_count
    FROM table_damage_to_fleet d
    WHERE 1 = 1
    """

    params = []

    # El móvil es opcional
    if filtros.get('movil'):
        sql += " AND d.Movil = ? "
        params.append(filtros['movil'])

    if filtros['uf'] != 'todos':
        sql += " AND d.UF = ? "
        params.append(filtros['uf'])

    if filtros['fecha_inicio']:
        sql += " AND d.Fecha_evento >= ? "
        params.append(filtros['fecha_inicio'])

    if filtros['fecha_fin']:
        fin = datetime.strptime(
            filtros['fecha_fin'],
            "%Y-%m-%d"
        ) + timedelta(days=1)

        sql += " AND d.Fecha_evento < ? "
        params.append(fin.strftime("%Y-%m-%d"))

    return sql, params


def _subquery_reparaciones(filtros):
    """Arma el SELECT de reparaciones/intervenciones con sus filtros."""

    sql = """
    SELECT
        p.Id AS id,
        p.Fecha_registro AS fecha,
        p.Movil,
        p.UF AS UF,
        p.Costo_intervencion AS costo,
        'REPARACIÓN' AS tipo,
        (
            SELECT COUNT(*)
            FROM table_intervenciones_files k
            WHERE k.RepairId = p.Id
        ) AS archivos_count
    FROM table_intervenciones p
    WHERE 1 = 1
    """

    params = []

    # El móvil es opcional
    if filtros.get('movil'):
        sql += " AND p.Movil = ? "
        params.append(filtros['movil'])

    if filtros['uf'] != 'todos':
        sql += " AND p.UF = ? "
        params.append(filtros['uf'])

    if filtros['fecha_inicio']:
        sql += " AND p.Fecha_registro >= ? "
        params.append(filtros['fecha_inicio'])

    if filtros['fecha_fin']:
        fin = datetime.strptime(
            filtros['fecha_fin'],
            "%Y-%m-%d"
        ) + timedelta(days=1)

        sql += " AND p.Fecha_registro < ? "
        params.append(fin.strftime("%Y-%m-%d"))

    return sql, params


def _construir_union(filtros):
    partes = []
    params = []

    if filtros['tipo'] in ('todos', 'danos'):
        sql_d, params_d = _subquery_danos(filtros)
        partes.append(sql_d)
        params.extend(params_d)

    if filtros['tipo'] in ('todos', 'reparaciones'):
        sql_r, params_r = _subquery_reparaciones(filtros)
        partes.append(sql_r)
        params.extend(params_r)

    sql_union = " UNION ALL ".join(partes)

    return sql_union, params

# 🔹 Mostrar la tabla principal
@Historico_movil.route('/')
@login_required
@requiere_permiso('Ingresar_danos_vs_reparaciones')

def index():
    filtros = _leer_filtros()
    movil_filtro = filtros['movil']

    registros = []
    total_registros = 0
    total_paginas = 0

   

    conn = connect()
    cursor = conn.cursor()

    sql_union, params = _construir_union(filtros)

    # 🔹 Conteo total para la paginación (respetando los filtros activos)
    query_conteo = f"SELECT COUNT(*) FROM ({sql_union}) AS conteo"
    cursor.execute(query_conteo, params)
    total_registros = cursor.fetchone()[0]
    total_paginas = max(1, math.ceil(total_registros / REGISTROS_POR_PAGINA))

    if filtros['page'] > total_paginas:
        filtros['page'] = total_paginas

    offset = (filtros['page'] - 1) * REGISTROS_POR_PAGINA

    # 🔹 Registros de la página actual, del más reciente al más antiguo
    query_pagina = f"""
        SELECT * FROM ({sql_union}) AS datos
        ORDER BY fecha DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
    cursor.execute(query_pagina, params + [offset, REGISTROS_POR_PAGINA])
    columns = [col[0] for col in cursor.description]
    registros = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # 🔹 Traer oper, mtto y svial únicamente para los registros de DAÑO
    for r in registros:
        if r['tipo'] != 'DAÑO':
            r['oper'] = []
            r['mtto'] = []
            r['svial'] = []
            continue

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

    conn.close()

    return render_template(
        "Front_historico_movil.html",
        registros=registros,
        movil_buscado=movil_filtro,
        filtros=filtros,
        pagina_actual=filtros['page'],
        total_paginas=total_paginas,
        total_registros=total_registros,
    )


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


# 🔹 Exportar a Excel el resultado actual del Histórico Móvil (respeta los filtros activos)
@Historico_movil.route('/exportar_excel')
@login_required
@requiere_permiso('Ingresar_danos_vs_reparaciones')
def exportar_excel():
    filtros = _leer_filtros()

    conn = connect()
    cursor = conn.cursor()

    wb = Workbook()
    primera_hoja = True

    # ---------- Hoja de DAÑOS ----------
    if filtros['tipo'] in ('todos', 'danos'):
        sql_d, params_d = _subquery_danos(filtros)
        cursor.execute(f"""
            SELECT dt.*
            FROM table_damage_to_fleet dt
            WHERE dt.Id IN (SELECT id FROM ({sql_d}) AS x)
            ORDER BY dt.Fecha_evento DESC
        """, params_d)
        columnas = [col[0] for col in cursor.description]
        filas = cursor.fetchall()

        ws = wb.active if primera_hoja else wb.create_sheet()
        ws.title = "Daños"
        primera_hoja = False
        ws.append(["Tipo"] + columnas)
        for fila in filas:
            ws.append(["DAÑO"] + list(fila))

    # ---------- Hoja de REPARACIONES / INTERVENCIONES ----------
    if filtros['tipo'] in ('todos', 'reparaciones'):
        sql_r, params_r = _subquery_reparaciones(filtros)
        cursor.execute(f"""
            SELECT
                i.[ID],
                i.[Movil],
                i.[UF],
                i.[Tipologia],
                i.[Zona_intervenida],
                i.[Parte_intervenida],
                i.[Costo_intervencion],
                i.[Usuario_registro],
                i.[Fecha_registro]
            FROM table_intervenciones i
            WHERE i.Id IN (SELECT id FROM ({sql_r}) AS x)
            ORDER BY i.Fecha_registro DESC
        """, params_r)
        columnas = [col[0] for col in cursor.description]
        filas = cursor.fetchall()

        ws = wb.active if primera_hoja else wb.create_sheet()
        ws.title = "Reparaciones"
        primera_hoja = False
        ws.append(["Tipo"] + columnas)
        for fila in filas:
            ws.append(["REPARACIÓN"] + list(fila))

    conn.close()

    if primera_hoja:
        # No se agregó ninguna hoja (no debería pasar, pero por seguridad)
        wb.active.title = "Sin datos"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nombre_archivo = f"historico_movil_{filtros['movil']}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


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