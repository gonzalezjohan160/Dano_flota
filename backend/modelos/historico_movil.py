"""Consultas del Histórico móvil: daños y reparaciones de cada vehículo.

Cada función recibe un cursor abierto. Las UF autorizadas llegan como parámetro
(las decide el controlador con la sesión), así este módulo no depende de Flask.
"""
from datetime import timedelta

from modelos.detalle_historicos import detalle_para_movil as gestiones_y_archivos_del_dano
from modelos.casos import CASO_CON_MOVIL, COLUMNAS_DEL_CASO
from modelos.casos import buscar_caso_completo as buscar_dano


# Columnas de la reparación con los nombres que usan la pantalla y el Excel.
COLUMNAS_DE_LA_REPARACION = """
    i.Id AS ID, i.movil AS Movil, CAST(m.UF AS varchar(3)) AS UF,
    m.Tipologia_Movil AS Tipologia, i.zona_intervenida AS Zona_intervenida,
    i.parte_intervenida AS Parte_intervenida, i.Costo_intervencion AS Costo_intervencion,
    i.Usuario_registro AS Usuario_registro, i.Fecha_registro AS Fecha_registro"""


def _filas_como_diccionarios(cursor):
    """Convierte el resultado del cursor en una lista de diccionarios {columna: valor}."""
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def _fila_como_diccionario(cursor, fila):
    """Convierte una fila en diccionario; sin fila devuelve un diccionario vacío."""
    if not fila:
        return {}
    columnas = [col[0] for col in cursor.description]
    return dict(zip(columnas, fila))


def _consulta_danos(filtros, ufs):
    """Arma el SELECT de daños con sus filtros. Devuelve (sql, parámetros)."""
    sql = """
    SELECT
        d.Id_damage AS id,
        d.Fecha_evento AS fecha,
        d.Movil AS Movil,
        CAST(m.UF AS varchar(3)) AS UF,
        (
            SELECT SUM(i.Costo)
            FROM proceso.v_BD6_table_info_mtto i
            WHERE i.Id_damage = d.Id_damage
        ) AS costo,
        'DAÑO' AS tipo,
        (
            SELECT COUNT(*)
            FROM flota.table_damage_files f
            WHERE f.Id_damage = d.Id_damage AND f.Modulo = 'Operaciones'
        ) AS archivos_count
    FROM flota.v_BD6_table_damage_to_fleet d
    INNER JOIN flota.table_Moviles m ON m.No_Movil = d.Movil
    WHERE d.eliminado = 0
    """

    parametros = []
    if ufs:
        marcadores = ", ".join("?" for _ in ufs)
        sql += f" AND m.UF IN ({marcadores}) "
        parametros.extend(int(uf) for uf in ufs)
    else:
        sql += " AND 1 = 0 "

    # El móvil es opcional
    if filtros.get('movil'):
        sql += " AND d.movil = ? "
        parametros.append(filtros['movil'])

    if filtros['uf'] != 'todos':
        sql += " AND m.UF = ? "
        parametros.append(int(filtros['uf']))

    if filtros['desde']:
        sql += " AND d.Fecha_evento >= ? "
        parametros.append(filtros['desde'])

    if filtros['hasta']:
        # Incluye todo el día final.
        sql += " AND d.Fecha_evento < ? "
        parametros.append(filtros['hasta'] + timedelta(days=1))

    return sql, parametros


def _consulta_reparaciones(filtros, ufs):
    """Arma el SELECT de reparaciones/intervenciones con sus filtros. Devuelve (sql, parámetros)."""
    sql = """
    SELECT
        p.ID AS id,
        p.Fecha_registro AS fecha,
        p.Movil AS Movil,
        CAST(mv.UF AS varchar(3)) AS UF,
        p.Costo_intervencion AS costo,
        'REPARACIÓN' AS tipo,
        (
            SELECT COUNT(*)
            FROM proceso.table_intervenciones_files k
            WHERE k.RepairId = p.ID
        ) AS archivos_count
    FROM proceso.v_BD6_table_intervenciones p
    INNER JOIN flota.table_Moviles mv ON mv.No_Movil = p.Movil
    WHERE 1 = 1
    """

    parametros = []
    if ufs:
        marcadores = ", ".join("?" for _ in ufs)
        sql += f" AND mv.UF IN ({marcadores}) "
        parametros.extend(int(uf) for uf in ufs)
    else:
        sql += " AND 1 = 0 "

    # El móvil es opcional
    if filtros.get('movil'):
        sql += " AND p.movil = ? "
        parametros.append(filtros['movil'])

    if filtros['uf'] != 'todos':
        sql += " AND mv.UF = ? "
        parametros.append(int(filtros['uf']))

    if filtros['desde']:
        sql += " AND p.Fecha_registro >= ? "
        parametros.append(filtros['desde'])

    if filtros['hasta']:
        # Incluye todo el día final.
        sql += " AND p.Fecha_registro < ? "
        parametros.append(filtros['hasta'] + timedelta(days=1))

    return sql, parametros


def _consulta_danos_y_reparaciones(filtros, ufs):
    """Une daños y reparaciones según el filtro 'tipo'. Devuelve (sql, parámetros)."""
    partes = []
    parametros = []

    if filtros['tipo'] in ('todos', 'danos'):
        sql_danos, parametros_danos = _consulta_danos(filtros, ufs)
        partes.append(sql_danos)
        parametros.extend(parametros_danos)

    if filtros['tipo'] in ('todos', 'reparaciones'):
        sql_reparaciones, parametros_reparaciones = _consulta_reparaciones(filtros, ufs)
        partes.append(sql_reparaciones)
        parametros.extend(parametros_reparaciones)

    return " UNION ALL ".join(partes), parametros


# ---------------------------------------------------------------- listado ---

def contar_registros(cursor, filtros, ufs):
    """Cantidad total de daños y reparaciones que cumplen los filtros (para paginar)."""
    sql_union, parametros = _consulta_danos_y_reparaciones(filtros, ufs)
    cursor.execute(f"SELECT COUNT(*) FROM ({sql_union}) AS conteo", parametros)
    return cursor.fetchone()[0]


def registros_de_la_pagina(cursor, filtros, ufs, desplazamiento, cantidad):
    """Registros de una página, del más reciente al más antiguo."""
    sql_union, parametros = _consulta_danos_y_reparaciones(filtros, ufs)
    cursor.execute(f"""
        SELECT * FROM ({sql_union}) AS datos
        ORDER BY fecha DESC
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, parametros + [desplazamiento, cantidad])
    return _filas_como_diccionarios(cursor)


# ----------------------------------------------------------------- daños ---


# ----------------------------------------------------------- reparaciones ---

def buscar_reparacion(cursor, id_reparacion):
    """Reparación completa (con la UF y la tipología de su móvil); diccionario vacío si no existe."""
    cursor.execute(f"""
        SELECT {COLUMNAS_DE_LA_REPARACION}
        FROM proceso.v_BD6_table_intervenciones i
        INNER JOIN flota.table_Moviles m ON m.No_Movil = i.movil
        WHERE i.Id = ?
    """, (id_reparacion,))
    return _fila_como_diccionario(cursor, cursor.fetchone())


def archivos_de_la_reparacion(cursor, id_reparacion):
    """Adjuntos de una reparación."""
    cursor.execute("""
        SELECT Id AS Id, 'reparaciones' AS TipoArchivo, FileName AS FileName,
               Fecha_subida AS Fecha_subida
        FROM proceso.table_intervenciones_files
        WHERE RepairId = ?
    """, (id_reparacion,))
    return _filas_como_diccionarios(cursor)


# ------------------------------------------------------- exportar a Excel ---

def danos_para_excel(cursor, filtros, ufs):
    """Todas las columnas de los daños filtrados. Devuelve (columnas, filas)."""
    sql_danos, parametros = _consulta_danos(filtros, ufs)
    cursor.execute(f"""
            SELECT {COLUMNAS_DEL_CASO}
            FROM {CASO_CON_MOVIL}
            WHERE d.Id_damage IN (SELECT id FROM ({sql_danos}) AS x)
            ORDER BY d.Fecha_evento DESC
        """, parametros)
    columnas = [col[0] for col in cursor.description]
    return columnas, cursor.fetchall()


def reparaciones_para_excel(cursor, filtros, ufs):
    """Columnas de las reparaciones filtradas que van al Excel. Devuelve (columnas, filas)."""
    sql_reparaciones, parametros = _consulta_reparaciones(filtros, ufs)
    cursor.execute(f"""
            SELECT {COLUMNAS_DE_LA_REPARACION}
            FROM proceso.v_BD6_table_intervenciones i
            INNER JOIN flota.table_Moviles m ON m.No_Movil = i.movil
            WHERE i.Id IN (SELECT id FROM ({sql_reparaciones}) AS x)
            ORDER BY i.Fecha_registro DESC
        """, parametros)
    columnas = [col[0] for col in cursor.description]
    return columnas, cursor.fetchall()
