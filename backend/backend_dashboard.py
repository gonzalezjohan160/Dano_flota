from conexiones import conexion_bd
from repositories.sesiones import abrir_conexion
from contextlib import closing
from flask import Blueprint, render_template, request
from config import connect
from backend_security import login_required, requiere_permiso, ufs_autorizadas_sesion
from logger import logger
from datetime import date
from fechas import FechaInvalida, leer_rango_fechas
from config import BASE_DIR
from modelos import dashboard as modelo_dashboard

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

    conn = abrir_conexion(connect)
    try:
        with conexion_bd(conn) as conexion:
            with closing(conexion.cursor()) as cursor:
                datos = modelo_dashboard.cargar_datos(
                    cursor, f_inicio, f_fin, ufs, uf_filtro
                )

        lista_uf = [fila[0] for fila in datos["lista_uf"]]
        rows_p = datos["rows_p"]
        rows_v = datos["rows_v"]
        rows_co = datos["rows_co"]
        ranking_registradores = [
            [fila[0], fila[1]] for fila in datos["ranking_registradores"]
        ]
        ranking = [
            [fila[0], fila[1], fila[2], float(fila[3])]
            for fila in datos["ranking"]
        ]
        ranking_rutas = [
            [fila[0], fila[1]] for fila in datos["ranking_rutas"]
        ]
        rows_franja = datos["rows_franja"]
        rrll_data = datos["rrll_data"]
        rows_vehiculos = datos["rows_vehiculos"]
        rows_zonas = datos["rows_zonas"]
        rows_ultimos_eventos = datos["rows_ultimos_eventos"]
        coords_rows = datos["coords_rows"]

        orden_franja = ['04:00-10:00', '10:00-16:00', '16:00-22:00', '22:00-04:00']
        dict_franja = {fila[0]: fila[1] for fila in rows_franja}
        franjas_final = [[franja, dict_franja.get(franja, 0)] for franja in orden_franja]

        # --- PROCESAMIENTO DE DATOS (ESTRUCTURA ORIGINAL) ---

        # Validación de ceros Pendientes
        registros_final = []
        for r in rows_p:
            if (r[2] + r[3] + r[4] + r[5]) > 0:
                registros_final.append([int(r[0]), int(r[1]), r[2], r[3], r[4], r[5]])

        # Sincronización Financiera (Costos vs Valores)
        costos_mtto = {(int(r[0]), int(r[1])): float(r[2]) for r in datos["rows_mtto"]}
        # Solo meses con registros; un total de cero sigue siendo un registro valido.
        mantenimiento_final = [[a, m, costos_mtto[(a, m)]] for a, m in sorted(costos_mtto)]
        dict_fin = {}
        for r in rows_v:
            key = (int(r[0]), int(r[1]))
            if key not in dict_fin:
                dict_fin[key] = {'valor': float(r[2]), 'oper': 0.0}
            else:
                dict_fin[key]['valor'] = float(r[2])

        for r in rows_co:
            key = (int(r[0]), int(r[1]))
            if key not in dict_fin:
                dict_fin[key] = {'valor': 0.0, 'oper': float(r[2])}
            else:
                dict_fin[key]['oper'] = float(r[2])

        sorted_keys = sorted(dict_fin.keys())
        valores_final = []
        operaciones_final = []
        for k in sorted_keys:
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
        mantenimiento_final = []
        registros_final, valores_final, operaciones_final, ranking, heat_data, lista_uf, franjas_final, rrll_final, ultimos_eventos, ranking_rutas, ranking_registradores, vehiculos_final, zonas_final = [], [], [], [], [], [], [], [], [], [], [], [], []
    

    # Retornamos todo incluyendo los valores actuales de los filtros para mantenerlos en el HTML
    return render_template('Front_dashboard.html', 
                           registros=registros_final, 
                           valores=valores_final, 
                           operaciones=operaciones_final,
                           mantenimiento=mantenimiento_final,
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
                           error_carga=error_carga,
                           dashboard_script_version=(
                               BASE_DIR / 'Static' / 'Script' / 'Script_dashboard.js'
                           ).stat().st_mtime_ns)
