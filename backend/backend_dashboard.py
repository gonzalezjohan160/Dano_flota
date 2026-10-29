from flask import Blueprint, render_template, request
from config import connect
from backend_security import login_required, requiere_permiso, ufs_autorizadas_sesion
from logger import logger
from datetime import date
from fechas import FechaInvalida, leer_rango_fechas
from config import BASE_DIR

Front_dashboard = Blueprint(
    'Front_dashboard',               # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)



@Front_dashboard.route('/')
@login_required
@requiere_permiso('Ingresar_dashboard')
def index():
    # 1. Obtener parámetros de los filtros desde la URL
    # Si no se envían, puedes definir fechas por defecto
    try:
        f_inicio, f_fin = leer_rango_fechas(request.args)
    except FechaInvalida as error:
        return str(error), 400
    # Sin fechas se usa el rango por defecto de siempre.
    f_inicio = f_inicio or date(2025, 1, 1)
    f_fin = f_fin or date(2026, 12, 31)
    uf_filtro = request.args.get('uf', '')
    ufs = ufs_autorizadas_sesion()
    error_carga = False

    conn = connect()
    cursor = conn.cursor()

    try:
        # --- CONSULTA PARA EL SELECT DE UF (Para llenar el filtro en el HTML) ---
        if ufs:
            marcadores_uf = ", ".join("?" for _ in ufs)
            cursor.execute(
                f"SELECT DISTINCT UF FROM table_damage_to_fleet WHERE UF IN ({marcadores_uf}) ORDER BY UF",
                list(ufs),
            )
            lista_uf = [row[0] for row in cursor.fetchall()]
        else:
            lista_uf = []

        # Preparar base de la condición WHERE para reutilizar
        # Usamos parámetros (?) para evitar inyecciones SQL
        params = [f_inicio, f_fin]
        # Los casos eliminados no cuentan en ningún indicador (decisión de negocio M-16).
        where_clause = "WHERE d.Fecha_evento BETWEEN ? AND ? AND ISNULL(d.eliminado, 0) = 0"
        if ufs:
            where_clause += f" AND d.UF IN ({marcadores_uf})"
            params.extend(ufs)
        else:
            where_clause += " AND 1 = 0"

        if uf_filtro:
            if uf_filtro in {str(uf) for uf in ufs}:
                where_clause += " AND d.UF = ?"
                params.append(int(uf_filtro))
            else:
                where_clause += " AND 1 = 0"

        # --- 1️⃣ CONSULTA: PENDIENTES (Gráfica 1) ---
        
        query_pendientes = f"""
        
                SELECT 
            YEAR(d.Fecha_evento), MONTH(d.Fecha_evento),

            COUNT(DISTINCT CASE WHEN d.estado_caso = 0
                AND o.estado_oper = 1
                AND t.estado_mtto = 1
                AND s.estado_svial = 1
                AND mf.DamageToFleetId IS NOT NULL
                THEN d.Id END) AS Labora,

            COUNT(DISTINCT CASE WHEN d.estado_caso = 0
                AND ISNULL(t.estado_mtto, 0) = 0
                THEN d.Id END) AS MTTO,

            COUNT(DISTINCT CASE WHEN d.estado_caso = 0
                AND ISNULL(o.estado_oper, 0) = 0
                THEN d.Id END) AS Oper,

            COUNT(DISTINCT CASE WHEN d.estado_caso = 0
                AND ISNULL(s.estado_svial, 0) = 0
                THEN d.Id END) AS Svial

        FROM table_damage_to_fleet d

        LEFT JOIN table_info_labora l
            ON l.Id_damage_to_fleet = d.Id

        LEFT JOIN table_info_mtto t
            ON t.Id_damage_to_fleet = d.Id

        LEFT JOIN table_info_oper o
            ON o.Id_damage_to_fleet = d.Id

        LEFT JOIN table_info_svial s
            ON s.Id_damage_to_fleet = d.Id

        LEFT JOIN (
            SELECT DISTINCT DamageToFleetId
            FROM table_mtto_files
        ) mf
            ON mf.DamageToFleetId = d.Id

        {where_clause}

        GROUP BY YEAR(d.Fecha_evento), MONTH(d.Fecha_evento)

        ORDER BY 1, 2  
        """
        
        
        cursor.execute(query_pendientes, params)
        rows_p = cursor.fetchall()
     

        # --- 2️⃣ CONSULTA: COSTOS MTTO (Gráfica 2 - Parte A) ---
        query_costos = f"""
            SELECT YEAR(d.Fecha_evento), MONTH(d.Fecha_evento), SUM(ISNULL(m.Costo,0)) 
            FROM table_info_mtto m
            JOIN table_damage_to_fleet d ON m.Id_damage_to_fleet = d.Id
            {where_clause}
            GROUP BY YEAR(d.Fecha_evento), MONTH(d.Fecha_evento)
        """
        cursor.execute(query_costos, params)
        rows_c = cursor.fetchall()

        # --- 3️⃣ CONSULTA: VALORES LABORA (Gráfica 2 - Parte B) ---
        query_valores = f"""
            SELECT YEAR(d.Fecha_evento), MONTH(d.Fecha_evento), SUM(ISNULL(l.Valor_conciliado,0)) 
            FROM table_info_labora l
            JOIN table_damage_to_fleet d ON l.Id_damage_to_fleet = d.Id
            {where_clause}
            GROUP BY YEAR(d.Fecha_evento), MONTH(d.Fecha_evento)
        """
        cursor.execute(query_valores, params)
        rows_v = cursor.fetchall()

        # --- 3️⃣.1 CONSULTA: COSTOS OPERACIONES (Gráfica 2 - Parte C) ---
        query_costos_oper = f"""
            SELECT YEAR(d.Fecha_evento), MONTH(d.Fecha_evento), SUM(ISNULL(o.costo_oper,0)) 
            FROM table_info_oper o
            JOIN table_damage_to_fleet d ON o.Id_damage_to_fleet = d.Id
            {where_clause}
            GROUP BY YEAR(d.Fecha_evento), MONTH(d.Fecha_evento)
        """
        cursor.execute(query_costos_oper, params)
        rows_co = cursor.fetchall()
        
        # --- CONSULTA: INSPECTORES ---
        query_registradores = f"""
            SELECT Registrador, COUNT(*) AS Cantidad
            FROM table_damage_to_fleet d
            {where_clause}
            AND Registrador IS NOT NULL
            AND Registrador <> ''
            GROUP BY Registrador
            ORDER BY COUNT(*) DESC
        """
        cursor.execute(query_registradores, params)
        ranking_registradores = [[row[0], row[1]] for row in cursor.fetchall()]

        # --- 4️⃣ CONSULTA: RANKING ---
        query_ranking = f"""
            SELECT TOP 10 d.Codigo, d.Nombre, COUNT(d.Id), SUM(ISNULL(m.Costo, 0))
            FROM table_damage_to_fleet d
            LEFT JOIN table_info_mtto m ON d.Id = m.Id_damage_to_fleet
            {where_clause}
            GROUP BY d.Codigo, d.Nombre 
            ORDER BY COUNT(d.Id) DESC
        """
        cursor.execute(query_ranking, params)
        ranking = [[row[0], row[1], row[2], float(row[3])] for row in cursor.fetchall()]
        
        # --- 5️⃣ CONSULTA: RUTAS CON MAS EVENTOS ---
        query_rutas = f"""
            SELECT Ruta, COUNT(*) AS Cantidad
            FROM table_damage_to_fleet d
            {where_clause}
            AND Ruta IS NOT NULL
            AND Ruta <> ''
            GROUP BY Ruta
            ORDER BY COUNT(*) DESC
        """
        cursor.execute(query_rutas, params)
        ranking_rutas = [[row[0], row[1]] for row in cursor.fetchall()]
        
        
        # --- CONSULTA: EVENTOS POR FRANJA HORARIA ---
        query_franja = f"""
            SELECT
            franja_horaria,
            COUNT(*) AS Cantidad
            FROM table_damage_to_fleet d
            {where_clause}
            GROUP BY franja_horaria
        """
        cursor.execute(query_franja, params)
        rows_franja = cursor.fetchall()
        
        orden_franja = ['04:00-10:00', '10:00-16:00', '16:00-22:00', '22:00-04:00']
        dict_franja = {fila[0]: fila[1] for fila in rows_franja}
        
        franjas_final = []
        for franja in orden_franja:
            franjas_final.append([franja, dict_franja.get(franja, 0)])
            
        
        # --- 6️⃣ CONSULTA: TOTAL CASOS VS CERRADOS ---
        query_rrll = f"""
            SELECT 
                YEAR(d.Fecha_evento) AS Year, MONTH(d.Fecha_evento) AS Month,
                COUNT(DISTINCT d.Id) AS Total_Casos,
                COUNT(DISTINCT CASE WHEN d.estado_caso = 1 THEN d.Id END) AS Casos_Cerrados
            FROM table_damage_to_fleet d
            {where_clause}
            GROUP BY YEAR(d.Fecha_evento), MONTH(d.Fecha_evento)
            ORDER BY YEAR(d.Fecha_evento), MONTH(d.Fecha_evento)
        """
        cursor.execute(query_rrll, params)
        rrll_data = cursor.fetchall()

        # --- 7️⃣ CONSULTA: EVENTOS POR VEHÍCULO (Móvil) ---
        query_vehiculos = f"""
            SELECT 
                d.Movil,
                COUNT(DISTINCT d.Id) AS Cantidad,
                SUM(ISNULL(m.Costo, 0)) AS ValorDanos
            FROM table_damage_to_fleet d
            LEFT JOIN table_info_mtto m ON m.Id_damage_to_fleet = d.Id
            {where_clause}
            AND d.Movil IS NOT NULL
            AND d.Movil <> ''
            GROUP BY d.Movil
            ORDER BY COUNT(DISTINCT d.Id) DESC
        """
        cursor.execute(query_vehiculos, params)
        rows_vehiculos = cursor.fetchall()

        # --- 8️⃣ CONSULTA: EVENTOS POR ZONA AFECTADA ---
        query_zonas = f"""
            SELECT 
                d.Zona_dano,
                COUNT(*) AS Cantidad
            FROM table_damage_to_fleet d
            {where_clause}
            AND d.Zona_dano IS NOT NULL
            AND d.Zona_dano <> ''
            GROUP BY d.Zona_dano
            ORDER BY COUNT(*) DESC
        """
        cursor.execute(query_zonas, params)
        rows_zonas = cursor.fetchall()
        
        # -- CONSULTA: ULTIMOS EVENTOS(62 días)
        if ufs:
            filtro_uf_ultimos = f"d.UF IN ({marcadores_uf})"
            params_ultimos = list(ufs)
        else:
            filtro_uf_ultimos = "1 = 0"
            params_ultimos = []
        if uf_filtro:
            if uf_filtro in {str(uf) for uf in ufs}:
                filtro_uf_ultimos += " AND d.UF = ?"
                params_ultimos.append(int(uf_filtro))
            else:
                filtro_uf_ultimos += " AND 1 = 0"

        query_ultimos_eventos = f"""
            SELECT
                d.Movil,
                d.Fecha_evento,
                d.Zona_dano,
                d.Parte_afectada
            FROM table_damage_to_fleet d
            WHERE d.Fecha_evento >= DATEADD(DAY, -62, GETDATE())
              AND ISNULL(d.eliminado, 0) = 0
              AND {filtro_uf_ultimos}
            ORDER BY d.Fecha_evento DESC
        """
        cursor.execute(query_ultimos_eventos, params_ultimos)
        rows_ultimos_eventos = cursor.fetchall()
        
        # --- 5️⃣ CONSULTA: MAPA DE CALOR ---
        query_mapa = f"SELECT [Direccion] FROM [table_damage_to_fleet] d {where_clause} AND [Direccion] IS NOT NULL"
        cursor.execute(query_mapa, params)
        coords_rows = cursor.fetchall()

        # --- PROCESAMIENTO DE DATOS (ESTRUCTURA ORIGINAL) ---

        # Validación de ceros Pendientes
        registros_final = []
        for r in rows_p:
            if (r[2] + r[3] + r[4] + r[5]) > 0:
                registros_final.append([int(r[0]), int(r[1]), r[2], r[3], r[4], r[5]])

        # Sincronización Financiera (Costos vs Valores)
        dict_fin = {}
        for r in rows_c:
            key = (int(r[0]), int(r[1]))
            dict_fin[key] = {'costo': float(r[2]), 'valor': 0.0, 'oper': 0.0}

        for r in rows_v:
            key = (int(r[0]), int(r[1]))
            if key not in dict_fin:
                dict_fin[key] = {'costo': 0.0, 'valor': float(r[2]), 'oper': 0.0}
            else:
                dict_fin[key]['valor'] = float(r[2])

        for r in rows_co:
            key = (int(r[0]), int(r[1]))
            if key not in dict_fin:
                dict_fin[key] = {'costo': 0.0, 'valor': 0.0, 'oper': float(r[2])}
            else:
                dict_fin[key]['oper'] = float(r[2])

        sorted_keys = sorted(dict_fin.keys())
        costos_final = []
        valores_final = []
        operaciones_final = []
        for k in sorted_keys:
            costos_final.append([k[0], k[1], dict_fin[k]['costo']])
            valores_final.append([k[0], k[1], dict_fin[k]['valor']])
            operaciones_final.append([k[0], k[1], dict_fin[k]['oper']])
            
        rrll_final = []
        for r in rrll_data:
            rrll_final.append([int(r[0]), int(r[1]), r[2], r[3]])    

        # Procesamiento Eventos por Vehículo
        vehiculos_final = []
        for r in rows_vehiculos:
            vehiculos_final.append([r[0], r[1], float(r[2])])

        # Procesamiento Eventos por Zona Afectada
        zonas_final = []
        for r in rows_zonas:
            zonas_final.append([r[0], r[1]])
            
        # Procesamiento Últimos Eventos
        ultimos_eventos = []
        
        for row in rows_ultimos_eventos:
            ultimos_eventos.append({
                "Movil":row[0],
                "Fecha_evento":row[1].strftime("%d/%m/%Y") if row[1] else "",
                "Zona_dano":row[2],
                "Parte_afectada":row[3]
             })    

        # Procesamiento Mapa
        heat_data = []
        coordenadas_invalidas = 0
        for row in coords_rows:
            if row[0] and ',' in row[0]:
                try:
                    parts = row[0].split(',')
                    lat, lon = float(parts[0].strip()), float(parts[1].strip())
                    heat_data.append([lat, lon])
                except ValueError:
                    # Dirección guardada sin "lat,lon" numéricos: se omite del mapa.
                    coordenadas_invalidas += 1
        if coordenadas_invalidas:
            logger.warning("dashboard_coordenadas_invalidas cantidad=%s", coordenadas_invalidas)

    except Exception:
        # Se registra en app.log y la pantalla avisa que no se pudieron cargar
        # los datos, en vez de mostrar el panel vacío como si no hubiera eventos.
        logger.exception("error_cargar_dashboard")
        error_carga = True
        registros_final, costos_final, valores_final, operaciones_final, ranking, heat_data, lista_uf, franjas_final, rrll_final, ultimos_eventos, ranking_rutas, ranking_registradores, vehiculos_final, zonas_final = [], [], [], [], [], [], [], [], [], [], [], [], [], []
    
    finally:
        cursor.close()
        conn.close()

    # Retornamos todo incluyendo los valores actuales de los filtros para mantenerlos en el HTML
    return render_template('Front_dashboard.html', 
                           registros=registros_final, 
                           costos=costos_final, 
                           valores=valores_final, 
                           operaciones=operaciones_final,
                           rrll=rrll_final,
                           franjas=franjas_final,
                           ranking=ranking,
                           ranking_rutas=ranking_rutas,
                           ranking_registradores=ranking_registradores, 
                           heatdata=heat_data,
                           lista_uf=lista_uf,
                           ultimos_eventos = ultimos_eventos,
                           vehiculos = vehiculos_final,
                           zonas = zonas_final,
                           f_inicio=f_inicio, f_fin=f_fin, uf_sel=uf_filtro,
                           error_carga=error_carga)
