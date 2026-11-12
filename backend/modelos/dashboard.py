"""Consultas del Dashboard.

Las consultas reciben el cursor y los filtros ya leídos por el controlador.
Este módulo no depende de Flask ni de la sesión.
"""


from datetime import date, datetime, timedelta, timezone


def meses_financieros(hoy=None):
    """Mes actual de Colombia y los cinco anteriores, en orden."""
    hoy = hoy or datetime.now(timezone(timedelta(hours=-5))).date()
    mes_actual = hoy.year * 12 + hoy.month - 1
    return [(mes // 12, mes % 12 + 1) for mes in range(mes_actual - 5, mes_actual + 1)]


# Toda consulta del Dashboard une el caso con su móvil (la UF es la del móvil).
CASO_CON_MOVIL = "flota.v_BD6_table_damage_to_fleet d INNER JOIN flota.table_Moviles mv ON mv.No_Movil = d.movil"


def _filtro_uf(ufs, uf_seleccionada):
    """(filtro, parametros) por UF autorizadas y UF elegida."""
    if not ufs:
        return "1 = 0", []
    marcadores = ", ".join("?" for _ in ufs)
    filtro = f"mv.UF IN ({marcadores})"
    parametros = [int(uf) for uf in ufs]
    if uf_seleccionada:
        if str(uf_seleccionada) in {str(uf) for uf in ufs}:
            filtro += " AND mv.UF = ?"
            parametros.append(int(uf_seleccionada))
        else:
            filtro += " AND 1 = 0"
    return filtro, parametros


def _filtro_principal(fecha_inicio, fecha_fin, ufs, uf_seleccionada):
    """Arma el filtro común por fechas y UF con parámetros SQL."""
    filtro_uf, parametros_uf = _filtro_uf(ufs, uf_seleccionada)
    filtro = f"WHERE d.fecha_evento BETWEEN ? AND ? AND d.eliminado = 0 AND {filtro_uf}"
    return filtro, [fecha_inicio, fecha_fin] + parametros_uf


def cargar_datos(cursor, fecha_inicio, fecha_fin, ufs, uf_seleccionada):
    """Ejecuta las consultas del Dashboard y devuelve sus resultados sin procesar."""
    datos = {}

    if ufs:
        marcadores_uf = ", ".join("?" for _ in ufs)
        cursor.execute(
            f"""SELECT DISTINCT CAST(mv.UF AS varchar(3)) AS UF
                FROM {CASO_CON_MOVIL}
                WHERE mv.UF IN ({marcadores_uf}) AND d.eliminado = 0 ORDER BY UF""",
            [int(uf) for uf in ufs],
        )
        datos["lista_uf"] = cursor.fetchall()
    else:
        datos["lista_uf"] = []

    where_clause, parametros = _filtro_principal(
        fecha_inicio, fecha_fin, ufs, uf_seleccionada
    )

    cursor.execute(f"""
        SELECT
            YEAR(d.fecha_evento), MONTH(d.fecha_evento),
            COUNT(DISTINCT CASE WHEN d.estado_caso = 0
                AND o.estado_oper = 1 AND t.estado_mtto = 1 AND s.estado_svial = 1
                AND mf.Id_damage IS NOT NULL THEN d.Id_damage END) AS Labora,
            COUNT(DISTINCT CASE WHEN d.estado_caso = 0
                AND ISNULL(t.estado_mtto, 0) = 0 THEN d.Id_damage END) AS MTTO,
            COUNT(DISTINCT CASE WHEN d.estado_caso = 0
                AND ISNULL(o.estado_oper, 0) = 0 THEN d.Id_damage END) AS Oper,
            COUNT(DISTINCT CASE WHEN d.estado_caso = 0
                AND ISNULL(s.estado_svial, 0) = 0 THEN d.Id_damage END) AS Svial
        FROM {CASO_CON_MOVIL}
        LEFT JOIN proceso.v_BD6_table_info_labora l ON l.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_mtto t ON t.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_oper o ON o.Id_damage = d.Id_damage
        LEFT JOIN proceso.v_BD6_table_info_svial s ON s.Id_damage = d.Id_damage
        LEFT JOIN (
            SELECT DISTINCT Id_damage FROM flota.table_damage_files WHERE modulo = 'Mantenimiento'
        ) mf ON mf.Id_damage = d.Id_damage
        {where_clause}
        GROUP BY YEAR(d.fecha_evento), MONTH(d.fecha_evento)
        ORDER BY 1, 2
    """, parametros)
    datos["rows_p"] = cursor.fetchall()

    meses = meses_financieros()
    datos["meses_financieros"] = meses
    inicio = date(*meses[0], 1)
    anio, mes = meses[-1]
    fin = date(anio + (mes == 12), mes % 12 + 1, 1)
    filtro_uf, parametros_uf = _filtro_uf(ufs, uf_seleccionada)
    where_financiero = (
        "WHERE d.fecha_evento >= ? AND d.fecha_evento < ? "
        f"AND d.eliminado = 0 AND {filtro_uf}"
    )
    parametros_financieros = [inicio, fin] + parametros_uf

    cursor.execute(f"""
        SELECT YEAR(d.fecha_evento), MONTH(d.fecha_evento),
               SUM(ISNULL(mt.Costo, 0)) AS costo_mtto
        FROM proceso.v_BD6_table_info_mtto mt
        JOIN {CASO_CON_MOVIL} ON mt.Id_damage = d.Id_damage
        {where_financiero}
        GROUP BY YEAR(d.fecha_evento), MONTH(d.fecha_evento)
        ORDER BY 1, 2
    """, parametros_financieros)
    datos["rows_mtto"] = cursor.fetchall()

    cursor.execute(f"""
        SELECT YEAR(d.fecha_evento), MONTH(d.fecha_evento), SUM(ISNULL(l.Valor_conciliado, 0))
        FROM proceso.v_BD6_table_info_labora l
        JOIN {CASO_CON_MOVIL} ON l.Id_damage = d.Id_damage
        {where_financiero}
        AND l.Tipo_cerrado LIKE N'%CONCILIACIÓN%'
        GROUP BY YEAR(d.fecha_evento), MONTH(d.fecha_evento)
    """, parametros_financieros)
    datos["rows_v"] = cursor.fetchall()

    cursor.execute(f"""
        SELECT YEAR(d.fecha_evento), MONTH(d.fecha_evento), SUM(ISNULL(o.costo_oper, 0))
        FROM proceso.v_BD6_table_info_oper o
        JOIN {CASO_CON_MOVIL} ON o.Id_damage = d.Id_damage
        {where_financiero}
        AND EXISTS (
            SELECT 1 FROM proceso.v_BD6_table_info_labora l
            WHERE l.Id_damage = d.Id_damage
              AND l.Tipo_cerrado LIKE N'%CONCILIACIÓN%'
        )
        GROUP BY YEAR(d.fecha_evento), MONTH(d.fecha_evento)
    """, parametros_financieros)
    datos["rows_co"] = cursor.fetchall()

    consultas = {
        "ranking_registradores": f"""
            SELECT d.Registrador AS Registrador, COUNT(*) AS Cantidad
            FROM {CASO_CON_MOVIL}
            {where_clause}
            AND d.Registrador IS NOT NULL AND d.Registrador <> ''
            GROUP BY d.Registrador ORDER BY COUNT(*) DESC
        """,
        "ranking": f"""
            SELECT TOP 10 d.Codigo, d.Nombre, COUNT(d.Id_damage), SUM(ISNULL(mt.Costo, 0))
            FROM {CASO_CON_MOVIL}
            LEFT JOIN proceso.v_BD6_table_info_mtto mt ON d.Id_damage = mt.Id_damage
            {where_clause}
            GROUP BY d.Codigo, d.Nombre ORDER BY COUNT(d.Id_damage) DESC
        """,
        "ranking_rutas": f"""
            SELECT d.ruta AS Ruta, COUNT(*) AS Cantidad
            FROM {CASO_CON_MOVIL}
            {where_clause}
            AND d.ruta IS NOT NULL AND d.ruta <> ''
            GROUP BY d.ruta ORDER BY COUNT(*) DESC
        """,
        "rows_franja": f"""
            SELECT d.franja_horaria, COUNT(*) AS Cantidad
            FROM {CASO_CON_MOVIL}
            {where_clause}
            GROUP BY d.franja_horaria
        """,
        "rrll_data": f"""
            SELECT YEAR(d.fecha_evento) AS Year, MONTH(d.fecha_evento) AS Month,
                   COUNT(DISTINCT d.Id_damage) AS Total_Casos,
                   COUNT(DISTINCT CASE WHEN d.estado_caso = 1 THEN d.Id_damage END) AS Casos_Cerrados
            FROM {CASO_CON_MOVIL}
            {where_financiero}
            GROUP BY YEAR(d.fecha_evento), MONTH(d.fecha_evento)
            ORDER BY YEAR(d.fecha_evento), MONTH(d.fecha_evento)
        """,
        "rows_vehiculos": f"""
            SELECT d.movil AS Movil, COUNT(DISTINCT d.Id_damage) AS Cantidad,
                   SUM(ISNULL(mt.Costo, 0)) AS ValorDanos
            FROM {CASO_CON_MOVIL}
            LEFT JOIN proceso.v_BD6_table_info_mtto mt ON mt.Id_damage = d.Id_damage
            {where_clause}
            GROUP BY d.movil ORDER BY COUNT(DISTINCT d.Id_damage) DESC
        """,
        "rows_zonas": f"""
            SELECT d.zona_dano AS Zona_dano, COUNT(*) AS Cantidad
            FROM {CASO_CON_MOVIL}
            {where_clause}
            AND d.zona_dano IS NOT NULL AND d.zona_dano <> ''
            GROUP BY d.zona_dano ORDER BY COUNT(*) DESC
        """,
    }

    for nombre, consulta in consultas.items():
        cursor.execute(consulta, parametros_financieros if nombre == "rrll_data" else parametros)
        datos[nombre] = cursor.fetchall()

    filtro_uf_ultimos, parametros_ultimos = _filtro_uf(ufs, uf_seleccionada)
    cursor.execute(f"""
        SELECT d.movil, d.fecha_evento, d.zona_dano, d.parte_afectada
        FROM {CASO_CON_MOVIL}
        WHERE d.fecha_evento >= DATEADD(DAY, -62, GETDATE())
          AND d.eliminado = 0
          AND {filtro_uf_ultimos}
        ORDER BY d.fecha_evento DESC
    """, parametros_ultimos)
    datos["rows_ultimos_eventos"] = cursor.fetchall()

    cursor.execute(
        f"SELECT d.direccion FROM {CASO_CON_MOVIL} {where_clause} AND d.direccion IS NOT NULL",
        parametros,
    )
    datos["coords_rows"] = cursor.fetchall()

    return datos
