"""Consultas de la bandeja (tabla principal) del módulo unificado.

Los filtros de cada módulo son textos fijos de este archivo y las UF se pasan
como parámetros "?"; nada de la petición se pega en la consulta.
"""

from modelos.laboral import ULTIMO_PROCESO_LABORAL_SQL

# Qué casos ve cada módulo, según el flujo del proceso de daño a flota.
FILTRO_PENDIENTE_MODULO = {
    # Operaciones, Mantenimiento y Seguridad Vial muestran ambas
    # bandejas; el filtro Estado del cliente decide si se ven los
    # pendientes o los gestionados.
    "Operaciones": "1 = 1",
    "Mtto": "1 = 1",
    "Svial": "1 = 1",
    "laboral": """
        NOT (
            estado_caso = 0
            AND EXISTS (
                SELECT 1 FROM proceso.v_BD6_table_info_oper as o_terminal
                WHERE o_terminal.Id_damage = base.Id
                  AND (
                      o_terminal.responsabilidad_operador = 'NO APLICA'
                      OR (
                          o_terminal.responsabilidad_operador = 'SI'
                          AND o_terminal.conciliacion = 'SI'
                          -- el costo solo se guarda cuando no_supera es verdadero.
                          AND o_terminal.costo_oper IS NOT NULL
                      )
                  )
                )
        )
        AND (
            EXISTS (
                SELECT 1 FROM proceso.v_BD6_table_info_labora as lm
                WHERE lm.Id_damage = base.Id
            )
            OR (
                tiene_oper = 1 AND tiene_svial = 1 AND estado_caso = 0
                AND (
                    EXISTS (
                        SELECT 1 FROM proceso.v_BD6_table_info_mtto as m2
                        WHERE m2.Id_damage = base.Id AND m2.usuario_id IS NOT NULL
                    )
                    OR EXISTS (
                        SELECT 1 FROM proceso.v_BD6_table_info_oper o3
                        WHERE o3.Id_damage = base.Id AND o3.responsabilidad_operador = 'NO'
                    )
                    OR EXISTS (
                        SELECT 1 FROM proceso.v_BD6_table_info_oper o4
                        WHERE o4.Id_damage = base.Id
                          AND o4.responsabilidad_operador = 'SI'
                          AND (o4.conciliacion IS NULL OR o4.conciliacion = 'NO')
                    )
                )
            )
        )
    """,
}


def listar_casos_del_modulo(cursor, ufs, modulo):
    """Casos no eliminados de las UF dadas que le corresponden al módulo.

    Devuelve una lista de diccionarios con las columnas de la consulta.
    """
    if ufs:
        marcadores = ", ".join("?" for _ in ufs)
        filtro_sql, parametros = f"m.UF IN ({marcadores})", [int(uf) for uf in ufs]
    else:
        filtro_sql, parametros = "1 = 0", []
    filtro_modulo = FILTRO_PENDIENTE_MODULO[modulo]
    # Solo Relaciones Laborales exige las tres gestiones iniciales completas.
    # Se decide en Python para no interpolar valores en el SQL.
    filtro_gestiones = (
        "AND estado_oper = 1 AND estado_mtto = 1 AND estado_svial = 1"
        if modulo == "laboral" else ""
    )

    if modulo == "laboral":
        comite = "(estado_caso = 0 AND CHARINDEX(',COMITE,', ',' + REPLACE(UPPER(ISNULL(pendiente_proceso_actual, '')), ' ', '') + ',') > 0)"
        filtro_modulo = f"({comite} OR (({filtro_modulo}) {filtro_gestiones}))"
        filtro_gestiones = ""

    query = f"""
        WITH base AS (
            SELECT
                d.Id_damage AS Id, d.Fecha_evento AS Fecha_evento, d.movil AS Movil,
                d.Fecha_registro AS Fecha_registro, CAST(m.UF AS varchar(3)) AS UF,
                d.Codigo AS Codigo, d.Nombre AS Nombre, d.ruta AS Ruta,
                m.Tipologia_Movil AS Tipologia, d.direccion AS Direccion, d.version_libre AS Version_libre,
                d.parte_afectada AS Parte_afectada, d.Dano_ocasionado AS Dano_ocasionado,
                d.zona_dano AS Zona_dano, d.Registrador AS Registrador,
                d.Centro_operaciones AS Centro_operaciones, d.area AS Area,
                d.estado_caso AS estado_caso,

                (SELECT COUNT(*) FROM flota.table_damage_files f WHERE f.Id_damage = d.Id_damage) AS archivos_count,

                (SELECT COUNT(*) FROM proceso.v_BD6_table_info_oper o WHERE o.Id_damage = d.Id_damage) AS tiene_oper,
                (SELECT COUNT(*) FROM proceso.v_BD6_table_info_mtto mt WHERE mt.Id_damage = d.Id_damage) AS tiene_mtto,
                (SELECT COUNT(*) FROM proceso.v_BD6_table_info_svial s WHERE s.Id_damage = d.Id_damage) AS tiene_svial,
                (SELECT COUNT(*) FROM proceso.v_BD6_table_info_labora l WHERE l.Id_damage = d.Id_damage) AS tiene_laboral,

                {ULTIMO_PROCESO_LABORAL_SQL} AS pendiente_proceso_actual,

                ISNULL((SELECT o.estado_oper FROM proceso.v_BD6_table_info_oper o WHERE o.Id_damage = d.Id_damage), 0) AS estado_oper,
                ISNULL((SELECT mt.estado_mtto FROM proceso.v_BD6_table_info_mtto mt WHERE mt.Id_damage = d.Id_damage), 0) AS estado_mtto,
                ISNULL((SELECT s.estado_svial FROM proceso.v_BD6_table_info_svial s WHERE s.Id_damage = d.Id_damage), 0) AS estado_svial,
                CASE WHEN EXISTS (
                    SELECT 1 FROM flota.table_damage_files mf WHERE mf.Id_damage = d.Id_damage AND mf.modulo = 'Mantenimiento'
                ) THEN 1 ELSE 0 END AS tiene_ot,
                (SELECT oreq.responsabilidad_operador FROM proceso.v_BD6_table_info_oper oreq
                 WHERE oreq.Id_damage = d.Id_damage) AS responsabilidad_operador,
                (SELECT oreq.conciliacion FROM proceso.v_BD6_table_info_oper oreq
                 WHERE oreq.Id_damage = d.Id_damage) AS conciliacion,
                d.estado_caso AS caso_cerrado,
                CASE WHEN EXISTS (
                    SELECT 1 FROM proceso.v_BD6_table_info_laboral_mult lm WHERE lm.Id_damage = d.Id_damage
                ) AND EXISTS (
                    SELECT 1 FROM proceso.v_BD6_table_info_labora l WHERE l.Id_damage = d.Id_damage
                ) THEN 1 ELSE 0 END AS cerrado_por_laboral,

                -- Fecha R. Laborales: la más reciente de las fechas de registro de
                -- Operaciones, Mtto y S.Vial, y de la orden de trabajo de Mtto. Solo
                -- tiene sentido una vez que las 3 ya existen (ver filtro de "laboral").
                (
                    SELECT MAX(fecha) FROM (
                        SELECT o.Fecha_registro AS fecha FROM proceso.v_BD6_table_info_oper o WHERE o.Id_damage = d.Id_damage
                        UNION ALL
                        SELECT mt.Fecha_registro FROM proceso.v_BD6_table_info_mtto mt WHERE mt.Id_damage = d.Id_damage
                        UNION ALL
                        SELECT s.Fecha_registro FROM proceso.v_BD6_table_info_svial s WHERE s.Id_damage = d.Id_damage
                        UNION ALL
                        SELECT mf.Fecha_subida FROM flota.table_damage_files mf
                        WHERE mf.Id_damage = d.Id_damage AND mf.modulo = 'Mantenimiento'
                    ) AS fechas_gestion
                ) AS Fecha_r_laboral

            FROM flota.v_BD6_table_damage_to_fleet d
            INNER JOIN flota.table_Moviles m ON m.No_Movil = d.movil
            WHERE {filtro_sql}
              AND d.eliminado = 0
        )
        SELECT * FROM base
        WHERE {filtro_modulo}
            {filtro_gestiones}
        ORDER BY Id DESC
    """

    cursor.execute(query, parametros)
    columnas = [c[0] for c in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def listar_moviles(cursor, ufs):
    """Móviles distintos con casos en las UF dadas, ordenados."""
    marcadores = ", ".join("?" for _ in ufs)
    cursor.execute(
        f"""SELECT DISTINCT d.movil
            FROM flota.v_BD6_table_damage_to_fleet d
            INNER JOIN flota.table_Moviles m ON m.No_Movil = d.movil
            WHERE m.UF IN ({marcadores})
            ORDER BY d.movil""",
        [int(uf) for uf in ufs],
    )
    return [fila[0] for fila in cursor.fetchall()]
