"""Consultas de Histórico de daños: filtros, tabla paginada y detalle del caso.

Los filtros se arman aquí con textos fijos y parámetros "?"; los valores que
escribe el usuario solo viajan como parámetros.
"""

from modelos.detalle_historicos import buscar_gestiones_basicas, _archivos, _una_fila, _todas_las_filas
from modelos.casos import CASO_CON_MOVIL
from modelos.casos import buscar_caso_completo as buscar_caso

ESTADOS_HISTORICO = ('abiertos', 'cerrados', 'eliminados')
# Al abrir el módulo no se muestran los casos eliminados.
ESTADOS_POR_DEFECTO = ('abiertos', 'cerrados')
CONDICION_ESTADO = {
    'abiertos': "(d.eliminado = 0 AND d.estado_caso = 0)",
    'cerrados': "(d.eliminado = 0 AND d.estado_caso = 1)",
    'eliminados': "(d.eliminado = 1)",
}


def agregar_filtros_comunes(filtros_sql, parametros, ufs, fecha_inicio, fecha_fin, filtro_uf):
    """Fechas del evento, UF autorizadas de la sesión y UF elegida (10 o 16).

    La UF es la del móvil: la consulta debe unir flota.table_Moviles con el alias m.
    """
    if fecha_inicio:
        filtros_sql.append("d.fecha_evento >= ?")
        parametros.append(fecha_inicio)
    if fecha_fin:
        # Incluye todo el día final.
        filtros_sql.append("d.fecha_evento < DATEADD(day, 1, CAST(? AS date))")
        parametros.append(fecha_fin)
    if ufs:
        marcadores = ", ".join("?" for _ in ufs)
        filtros_sql.append(f"m.UF IN ({marcadores})")
        parametros.extend(int(uf) for uf in ufs)
    else:
        filtros_sql.append("1 = 0")
    if filtro_uf in ('10', '16'):
        filtros_sql.append("m.UF = ?")
        parametros.append(int(filtro_uf))


def agregar_filtro_estados(filtros_sql, estados):
    condiciones = [CONDICION_ESTADO[e] for e in ESTADOS_HISTORICO if e in estados]
    filtros_sql.append("(" + " OR ".join(condiciones) + ")" if condiciones else "1 = 0")


def filtro_de_la_tabla(ufs, fecha_inicio, fecha_fin, filtro_uf, estados, filtros):
    """(where_sql, parametros) de la tabla. filtros: id, fecha, movil, codigo, nombre."""
    filtros_sql, parametros = [], []
    agregar_filtros_comunes(filtros_sql, parametros, ufs, fecha_inicio, fecha_fin, filtro_uf)
    agregar_filtro_estados(filtros_sql, estados)
    if filtros['id']:
        filtros_sql.append("CAST(d.Id_damage AS varchar(20)) LIKE ?")
        parametros.append(f"%{filtros['id']}%")
    if filtros['fecha']:
        filtros_sql.append("CAST(d.fecha_evento AS date) = ?")
        parametros.append(filtros['fecha'])
    if filtros['movil']:
        filtros_sql.append("d.movil LIKE ?")
        parametros.append(f"%{filtros['movil']}%")
    if filtros['codigo']:
        filtros_sql.append("d.Codigo LIKE ?")
        parametros.append(f"%{filtros['codigo']}%")
    if filtros['nombre']:
        filtros_sql.append("d.Nombre LIKE ?")
        parametros.append(f"%{filtros['nombre']}%")
    return " AND ".join(filtros_sql), parametros


def contar_casos(cursor, where_sql, parametros):
    cursor.execute(f"SELECT COUNT(*) FROM {CASO_CON_MOVIL} WHERE {where_sql}", parametros)
    return cursor.fetchone()[0]


def listar_pagina(cursor, where_sql, parametros, desplazamiento, cantidad, contar_adjuntos_laborales):
    """Una página de la tabla, en UNA consulta y con las columnas que muestra (B-12)."""
    # Los documentos de RRLL solo cuentan para quien puede abrirlos (M-17).
    modulos_contados = (
        "('Operaciones', 'Mantenimiento', 'Seguridad vial', 'Laboral')"
        if contar_adjuntos_laborales else "('Operaciones', 'Mantenimiento', 'Seguridad vial')"
    )

    # Los filtros se aplican antes del OFFSET para no cargar todo el histórico;
    # el resto de cada caso lo trae buscar_gestiones_y_adjuntos().
    query_main = f"""
            SELECT
                d.Id_damage AS Id, d.fecha_evento AS Fecha_evento, d.movil AS Movil,
                d.fecha_registro AS Fecha_registro, CAST(m.UF AS varchar(3)) AS UF,
                d.Codigo AS Codigo, d.Nombre AS Nombre,
                d.estado_caso AS estado_caso,
                d.eliminado AS eliminado,
                CASE WHEN EXISTS (SELECT 1 FROM proceso.v_BD6_table_info_oper o WHERE o.Id_damage = d.Id_damage)
                     THEN 1 ELSE 0 END AS tiene_oper,
                CASE WHEN EXISTS (SELECT 1 FROM proceso.v_BD6_table_info_mtto mt WHERE mt.Id_damage = d.Id_damage)
                     THEN 1 ELSE 0 END AS tiene_mtto,
                CASE WHEN EXISTS (SELECT 1 FROM proceso.v_BD6_table_info_svial s WHERE s.Id_damage = d.Id_damage)
                     THEN 1 ELSE 0 END AS tiene_svial,
                CASE WHEN d.estado_caso = 1 THEN COALESCE(
                    (SELECT MAX(l.Fecha_registro) FROM proceso.v_BD6_table_info_labora l WHERE l.Id_damage = d.Id_damage),
                    cierre_modulos.Fecha_cierre
                ) END AS Fecha_cierre,
                (
                    SELECT COUNT(*) FROM flota.table_damage_files f
                    WHERE f.Id_damage = d.Id_damage AND f.modulo IN {modulos_contados}
                ) AS archivos_count
            FROM {CASO_CON_MOVIL}
            OUTER APPLY (
                SELECT MAX(fecha_registro) AS Fecha_cierre
                FROM (
                    SELECT o.Fecha_registro FROM proceso.v_BD6_table_info_oper o WHERE o.Id_damage = d.Id_damage
                    UNION ALL
                    SELECT mt.Fecha_registro FROM proceso.v_BD6_table_info_mtto mt WHERE mt.Id_damage = d.Id_damage
                    UNION ALL
                    SELECT s.Fecha_registro FROM proceso.v_BD6_table_info_svial s WHERE s.Id_damage = d.Id_damage
                ) AS fechas_modulos
            ) AS cierre_modulos
            WHERE {where_sql}
            ORDER BY d.Id_damage ASC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    cursor.execute(query_main, parametros + [desplazamiento, cantidad])
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def buscar_gestiones_y_adjuntos(cursor, id_damage):
    """Gestión de cada módulo, historial de RRLL, correcciones y adjuntos del caso."""
    gestiones = buscar_gestiones_basicas(cursor, id_damage)
    cursor.execute("""
        SELECT Tipo_cerrado AS Tipo_cerrado, Valor_conciliado AS Valor_conciliado,
               Fecha_registro AS Fecha_registro, Usuario_registro_labora AS Usuario_registro_labora
        FROM proceso.v_BD6_table_info_labora
        WHERE Id_damage = ?
    """, (id_damage,))
    laboral = _una_fila(cursor)

    cursor.execute("""
        SELECT Fecha_presentacion AS Fecha_presentacion, Pendiente_proceso AS Pendiente_proceso,
               Observaciones_rrll AS Observaciones_rrll, Fecha_registro AS Fecha_registro,
               Usuario_registro_laboral AS Usuario_registro_laboral
        FROM proceso.v_BD6_table_info_laboral_mult
        WHERE Id_damage = ?
    """, (id_damage,))
    laboralm = _todas_las_filas(cursor)

    cursor.execute("""
        SELECT Tabla_Afectada AS Tabla_Afectada, Campo_Modificado AS Campo_Modificado,
               Valor_Anterior AS Valor_Anterior, Valor_Nuevo AS Valor_Nuevo,
               Usuario_Modifica AS Usuario_Modifica, Fecha_Modificacion AS Fecha_Modificacion
        FROM proceso.v_BD6_table_auditoria_correcciones
        WHERE Id_damage = ?
    """, (id_damage,))
    correcciones = _todas_las_filas(cursor)

    return {
        **gestiones, "laboral": laboral, "laboralm": laboralm,
        "correcciones": correcciones,
        "archivos": _archivos(cursor, id_damage, "Operaciones", "operaciones"),
        "archivos_laboral": _archivos(cursor, id_damage, "Laboral", "laboral"),
        "archivos_mtto": _archivos(cursor, id_damage, "Mantenimiento", "mtto"),
        "archivos_svial": _archivos(cursor, id_damage, "Seguridad vial", "svial"),
    }
