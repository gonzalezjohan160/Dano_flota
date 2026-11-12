"""Consultas de la exportación a Excel de Histórico de daños (general y de RRLL)."""
from modelos.historico_danos import agregar_filtro_estados, agregar_filtros_comunes

from modelos.casos import CASO_CON_MOVIL
from modelos.laboral import ULTIMO_PROCESO_LABORAL_SQL, COMITE_RRLL_SQL

# Mismo universo de RRLL que la bandeja de RRLL (modelos/bandeja.py): casos con
# entrada registrada en RRLL o candidatos pendientes del flujo actual.
# Se usan EXISTS para no duplicar un caso con varias gestiones RRLL.
FILTRO_UNIVERSO_RRLL = """(
    NOT (
        d.estado_caso = 0
        AND EXISTS (
            SELECT 1 FROM proceso.v_BD6_table_info_oper o_terminal
            WHERE o_terminal.Id_damage = d.Id_damage
              AND (
                  o_terminal.responsabilidad_operador = 'NO APLICA'
                  OR (
                      o_terminal.responsabilidad_operador = 'SI'
                      AND o_terminal.conciliacion = 'SI'
                      AND o_terminal.costo_oper IS NOT NULL
                  )
              )
        )
    )
    AND (
        EXISTS (
            SELECT 1 FROM proceso.v_BD6_table_info_laboral_mult lm
            WHERE lm.Id_damage = d.Id_damage
        ) OR (
            EXISTS (SELECT 1 FROM proceso.v_BD6_table_info_oper o WHERE o.Id_damage = d.Id_damage)
            AND EXISTS (SELECT 1 FROM proceso.v_BD6_table_info_svial s WHERE s.Id_damage = d.Id_damage)
            AND d.estado_caso = 0
            AND (
                EXISTS (
                    SELECT 1 FROM proceso.v_BD6_table_info_mtto m2
                    WHERE m2.Id_damage = d.Id_damage
                      AND m2.usuario_id IS NOT NULL
                )
                OR EXISTS (
                    SELECT 1 FROM proceso.v_BD6_table_info_oper o3
                    WHERE o3.Id_damage = d.Id_damage
                      AND o3.responsabilidad_operador = 'NO'
                )
                OR EXISTS (
                    SELECT 1 FROM proceso.v_BD6_table_info_oper o4
                    WHERE o4.Id_damage = d.Id_damage
                      AND o4.responsabilidad_operador = 'SI'
                      AND (o4.conciliacion IS NULL OR o4.conciliacion = 'NO')
                )
            )
        )
    ))"""

FILTRO_UNIVERSO_RRLL = f"({COMITE_RRLL_SQL} OR {FILTRO_UNIVERSO_RRLL})"

# Columnas que solo necesita el cálculo del estado de RRLL.
COLUMNAS_ESTADO_RRLL = f""",
               CASE WHEN EXISTS (
                   SELECT 1 FROM proceso.v_BD6_table_info_laboral_mult lm WHERE lm.Id_damage = d.Id_damage
               ) AND EXISTS (
                   SELECT 1 FROM proceso.v_BD6_table_info_labora l2 WHERE l2.Id_damage = d.Id_damage
               ) THEN 1 ELSE 0 END AS cerrado_por_laboral,
               ISNULL(o.estado_oper, 0) AS estado_oper,
               ISNULL(mt.estado_mtto, 0) AS estado_mtto,
               ISNULL(s.estado_svial, 0) AS estado_svial,
               {ULTIMO_PROCESO_LABORAL_SQL} AS pendiente_proceso_actual,
               CASE WHEN EXISTS (
                   SELECT 1 FROM flota.table_damage_files mf WHERE mf.Id_damage = d.Id_damage AND mf.Modulo = 'Mantenimiento'
               ) THEN 1 ELSE 0 END AS tiene_ot,
               (SELECT MAX(mf.Fecha_subida) FROM flota.table_damage_files mf
                WHERE mf.Id_damage = d.Id_damage AND mf.Modulo = 'Mantenimiento') AS fecha_r_laborales"""


def filtro_de_la_exportacion(ufs, fecha_inicio, fecha_fin, filtro_uf, estados, universo_rrll):
    """(where_sql, parametros). Los casos eliminados nunca se exportan."""
    filtros_sql = ["d.eliminado = 0"]
    parametros = []
    agregar_filtros_comunes(filtros_sql, parametros, ufs, fecha_inicio, fecha_fin, filtro_uf)
    if universo_rrll:
        filtros_sql.append(FILTRO_UNIVERSO_RRLL)
    else:
        agregar_filtro_estados(filtros_sql, estados)
    return " AND ".join(filtros_sql), parametros


def listar_para_exportar(cursor, where_sql, parametros, con_estado_rrll):
    """Casos con la gestión de cada módulo (una sola consulta) y el historial de
    RRLL agrupado por caso: (registros, laboral_por_caso)."""
    columnas_laboral = COLUMNAS_ESTADO_RRLL if con_estado_rrll else ""
    cursor.execute(f"""
        SELECT d.Id_damage AS Id, d.fecha_evento AS Fecha_evento, d.movil AS Movil,
               d.Codigo AS Codigo, d.Nombre AS Nombre, d.area AS Area, d.ruta AS Ruta,
               d.version_libre AS Version_libre, d.zona_dano AS Zona_dano,
               d.parte_afectada AS Parte_afectada, d.Dano_ocasionado AS Dano_ocasionado,
               d.Centro_operaciones AS Centro_operaciones, d.Registrador AS Registrador,
               d.fecha_registro AS Fecha_registro, d.direccion AS Direccion,
               d.estado_caso AS estado_caso,
               o.Observaciones_operaciones AS oper_observaciones, o.rev_error AS oper_rev_error,
               o.observaciones_correctivos AS oper_correctivos, o.costo_oper AS oper_costo,
               o.responsabilidad_operador AS oper_responsabilidad, o.conciliacion AS oper_conciliacion,
               o.Fecha_registro AS oper_fecha, o.Usuario_registro_oper AS oper_usuario,
               mt.Costo AS mtto_costo, mt.observaciones AS mtto_observaciones,
               mt.dano_adicional AS mtto_dano_adicional, mt.Fecha_registro AS mtto_fecha,
               mt.Usuario_registro_mtto AS mtto_usuario,
               s.Observaciones_svial AS svial_observaciones,
               s.valor_conciliado_terceros AS svial_valor_terceros,
               s.conciliado_a_favor AS svial_a_favor, s.Fecha_registro AS svial_fecha,
               s.Usuario_registro_svial AS svial_usuario,
               l.Tipo_cerrado AS lab_tipo_cerrado, l.Valor_conciliado AS lab_valor_conciliado,
               l.Fecha_registro AS lab_fecha, l.Usuario_registro_labora AS lab_usuario
               {columnas_laboral}
        FROM {CASO_CON_MOVIL}
        LEFT JOIN proceso.v_BD6_table_info_oper o ON o.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_mtto mt ON mt.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_svial s ON s.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_labora l ON l.Id_damage = d.Id_damage
        WHERE {where_sql}
        ORDER BY d.Id_damage ASC
    """, parametros)
    columnas = [col[0] for col in cursor.description]
    registros = [dict(zip(columnas, row)) for row in cursor.fetchall()]

    # Historial de RRLL de todos los casos exportados, en una sola consulta.
    cursor.execute(f"""
        SELECT lm.Id_damage AS Id_damage_to_fleet, lm.Fecha_presentacion AS Fecha_presentacion,
               lm.Pendiente_proceso AS Pendiente_proceso, lm.Observaciones_rrll AS Observaciones_rrll,
               lm.Fecha_registro AS Fecha_registro, lm.Usuario_registro_laboral AS Usuario_registro_laboral
        FROM proceso.v_BD6_table_info_laboral_mult lm
        WHERE lm.Id_damage IN (SELECT d.Id_damage FROM {CASO_CON_MOVIL} WHERE {where_sql})
        ORDER BY lm.Id_damage, lm.Fecha_registro
    """, parametros)
    columnas_lab = [col[0] for col in cursor.description]
    laboral_por_caso = {}
    for row in cursor.fetchall():
        item = dict(zip(columnas_lab, row))
        laboral_por_caso.setdefault(item["Id_damage_to_fleet"], []).append(item)
    return registros, laboral_por_caso
