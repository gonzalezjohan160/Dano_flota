"""CONTROLADOR del Histórico móvil (daños y reparaciones por vehículo).

Lee la petición, aplica permisos y UF, llama al modelo (modelos/historico_movil.py,
donde está el SQL) y devuelve la respuesta: la plantilla, JSON o el Excel
(vistas/excel.py). Las conexiones se abren con closing(), que las cierra siempre,
también si ocurre un error.
"""
from repositories.sesiones import sesion_bd
from contextlib import closing

from flask import Blueprint, render_template, request, jsonify, send_file, abort
import math
from config import connect
from fechas import FechaInvalida, leer_rango_fechas
from backend_security import (
    login_required,
    requiere_permiso,
    usuario_puede_acceder_uf,
    ufs_autorizadas_sesion,
)
from config import BASE_DIR
from modelos import historico_movil as modelo
from vistas.excel import crear_libro_excel

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
    fecha_inicio, fecha_fin = leer_rango_fechas(request.args)

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
        # Texto AAAA-MM-DD ya validado para la pantalla; date para las consultas.
        'fecha_inicio': fecha_inicio.isoformat() if fecha_inicio else '',
        'fecha_fin': fecha_fin.isoformat() if fecha_fin else '',
        'desde': fecha_inicio,
        'hasta': fecha_fin,
        'page': page,
    }


# 🔹 Mostrar la tabla principal
@Historico_movil.route('/')
@login_required
@requiere_permiso('Ingresar_danos_vs_reparaciones')
def index():
    try:
        filtros = _leer_filtros()
    except FechaInvalida as error:
        return str(error), 400
    ufs = ufs_autorizadas_sesion()

    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:

        # 🔹 Conteo total para la paginación (respetando los filtros activos)
        total_registros = modelo.contar_registros(cursor, filtros, ufs)
        total_paginas = max(1, math.ceil(total_registros / REGISTROS_POR_PAGINA))

        if filtros['page'] > total_paginas:
            filtros['page'] = total_paginas

        desplazamiento = (filtros['page'] - 1) * REGISTROS_POR_PAGINA

        # 🔹 Registros de la página actual. El listado solo muestra estas columnas;
        # Operaciones, Mantenimiento y S. Vial de cada daño los trae /detalle/<id> (B-12).
        registros = modelo.registros_de_la_pagina(
            cursor, filtros, ufs, desplazamiento, REGISTROS_POR_PAGINA)

    return render_template(
        "Front_historico_movil.html",
        registros=registros,
        movil_buscado=filtros['movil'],
        filtros=filtros,
        pagina_actual=filtros['page'],
        total_paginas=total_paginas,
        total_registros=total_registros,
    )


@Historico_movil.route('/detalle/<int:id_damage>')
@login_required
@requiere_permiso('Ingresar_danos_vs_reparaciones')
def detalle(id_damage):
    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:

        registro = modelo.buscar_dano(cursor, id_damage)
        if not registro:
            abort(404)
        if not usuario_puede_acceder_uf(registro.get("UF")):
            abort(403)
        # Un caso eliminado no se muestra en el Histórico móvil (decisión de negocio M-16).
        if registro.get("eliminado"):
            abort(404)

        gestiones = modelo.gestiones_y_archivos_del_dano(cursor, id_damage)

    return jsonify({
        "registro": registro,
        "oper": gestiones["oper"],
        "svial": gestiones["svial"],
        "mtto": gestiones["mtto"],
        "archivos": gestiones["archivos"]
    })


@Historico_movil.route('/detalle_reparacion/<int:id>')
@login_required
@requiere_permiso('Ingresar_danos_vs_reparaciones')
def detalle_reparacion(id):
    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:

        registro = modelo.buscar_reparacion(cursor, id)
        if not registro:
            abort(404)
        if not usuario_puede_acceder_uf(registro.get("UF")):
            abort(403)

        archivos = modelo.archivos_de_la_reparacion(cursor, id)

    return jsonify({
        "registro": registro,
        "archivos": archivos
    })


# 🔹 Exportar a Excel el resultado actual del Histórico Móvil (respeta los filtros activos)
@Historico_movil.route('/exportar_excel')
@login_required
@requiere_permiso('Ingresar_danos_vs_reparaciones')
def exportar_excel():
    try:
        filtros = _leer_filtros()
    except FechaInvalida as error:
        return str(error), 400
    ufs = ufs_autorizadas_sesion()

    hojas = []
    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:

        # ---------- Hoja de DAÑOS ----------
        if filtros['tipo'] in ('todos', 'danos'):
            columnas, filas = modelo.danos_para_excel(cursor, filtros, ufs)
            hojas.append({"titulo": "Daños", "etiqueta": "DAÑO", "columnas": columnas, "filas": filas})

        # ---------- Hoja de REPARACIONES / INTERVENCIONES ----------
        if filtros['tipo'] in ('todos', 'reparaciones'):
            columnas, filas = modelo.reparaciones_para_excel(cursor, filtros, ufs)
            hojas.append({"titulo": "Reparaciones", "etiqueta": "REPARACIÓN", "columnas": columnas, "filas": filas})

    nombre_archivo = f"historico_movil_{filtros['movil']}.xlsx"
    return send_file(
        crear_libro_excel(hojas),
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
