"""Histórico de daños: tabla paginada con filtros, detalle del caso y exportación a Excel.

El SQL está en modelos/historico_danos.py y modelos/historico_danos_exportacion.py,
el Excel en vistas/excel_historico_danos.py y el estado de RRLL en
servicios/flujo_caso.py. Aquí solo se lee la petición, se aplican permisos y UF,
se abre y cierra la conexión y se responde.
"""
from repositories.sesiones import sesion_bd
from contextlib import closing
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, send_file, abort, session

from config import connect
from fechas import FechaInvalida, leer_rango_fechas, parse_fecha
from logger import logger
from backend_security import (
    login_required,
    requiere_permiso,
    usuario_puede_acceder_uf,
    ufs_autorizadas_sesion,
    puede_ver_adjuntos_laborales,
)
from config import BASE_DIR
from modelos import historico_danos as modelo_historico
from modelos import historico_danos_exportacion as modelo_exportacion
from modelos.historico_danos import ESTADOS_HISTORICO, ESTADOS_POR_DEFECTO
from servicios.flujo_caso import estado_rrll_para_exportacion
from vistas.excel_historico_danos import crear_excel_historico

Historico_danos = Blueprint(
    'Historico_danos',               # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)

REGISTROS_POR_PAGINA = 30

# Filtro con formato incorrecto; el mensaje se puede mostrar al usuario.
FiltroInvalido = FechaInvalida


def _leer_fechas():
    """Fechas opcionales del evento (AAAA-MM-DD). Vacías = sin filtro de fecha."""
    return leer_rango_fechas(request.args)


def _leer_estados():
    """Estados marcados en las casillas; si no llega ninguno se usan los de por defecto."""
    estados = [e for e in request.args.getlist('estado') if e in ESTADOS_HISTORICO]
    return list(dict.fromkeys(estados)) or list(ESTADOS_POR_DEFECTO)


def _formatear_fecha(valor, id_caso, evento_log, si_invalida=None):
    """dd/mm/aaaa hh:mm:ss para la tabla. Acepta datetime o texto ISO."""
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M:%S")
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor.split('.')[0]).strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            logger.warning(evento_log, id_caso)
            return si_invalida
    return None


# 🔹 Mostrar la tabla principal
@Historico_danos.route('/')
@login_required
@requiere_permiso('Ingresar_historico_danos')
def index():
    try:
        fecha_inicio, fecha_fin = _leer_fechas()
        fecha_exacta = parse_fecha(request.args.get('f_fecha'), "la columna Fecha")
    except FiltroInvalido as error:
        return str(error), 400
    estados = _leer_estados()

    filtro_uf = request.args.get('filtro_uf', 'todos')
    filtros = {
        'id': request.args.get('f_id', '').strip(),
        'fecha': fecha_exacta.isoformat() if fecha_exacta else '',
        'movil': request.args.get('f_movil', '').strip(),
        'codigo': request.args.get('f_codigo', '').strip(),
        'nombre': request.args.get('f_nombre', '').strip(),
    }
    try:
        pagina = max(1, int(request.args.get('pagina', 1)))
    except ValueError:
        pagina = 1

    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
        where_sql, parametros = modelo_historico.filtro_de_la_tabla(
            ufs_autorizadas_sesion(), fecha_inicio, fecha_fin, filtro_uf, estados, filtros)
        total_registros = modelo_historico.contar_casos(cursor, where_sql, parametros)
        total_paginas = max(1, (total_registros + REGISTROS_POR_PAGINA - 1) // REGISTROS_POR_PAGINA)
        pagina = min(pagina, total_paginas)
        desplazamiento = (pagina - 1) * REGISTROS_POR_PAGINA
        registros = modelo_historico.listar_pagina(
            cursor, where_sql, parametros, desplazamiento, REGISTROS_POR_PAGINA, puede_ver_adjuntos_laborales())

    for r in registros:
        fecha = r.get('Fecha_evento')
        r['fecha'] = fecha.strftime("%Y-%m-%d %H:%M:%S") if fecha else None
        r['fecha_datetime'] = fecha
        # Si la fecha de registro no se puede leer, se muestra la del evento.
        r['fecha_r'] = _formatear_fecha(r.pop('Fecha_registro'), r.get('Id'),
                                        "historico_fecha_registro_invalida id=%s", si_invalida=r['fecha'])
        r['fecha_cierre'] = _formatear_fecha(r.pop('Fecha_cierre'), r.get('Id'),
                                             "historico_fecha_cierre_invalida id=%s")

    return render_template(
        "Front_historico_danos.html",
        registros=registros,
        pagina=pagina,
        total_registros=total_registros,
        fecha_inicio=fecha_inicio.isoformat() if fecha_inicio else "",
        fecha_fin=fecha_fin.isoformat() if fecha_fin else "",
        filtro_uf=filtro_uf,
        estados=estados,
        filtros=filtros
    )


@Historico_danos.route('/detalle/<int:id_damage>')
@login_required
@requiere_permiso('Ingresar_historico_danos')
def detalle(id_damage):
    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
        registro = modelo_historico.buscar_caso(cursor, id_damage)
        if not registro:
            abort(404)
        if not usuario_puede_acceder_uf(registro.get("UF")):
            abort(403)
        gestiones = modelo_historico.buscar_gestiones_y_adjuntos(cursor, id_damage)

    # Los documentos de Relaciones Laborales solo se listan a RRLL.
    if not puede_ver_adjuntos_laborales():
        gestiones["archivos_laboral"] = []

    return jsonify({"registro": registro, **gestiones})


@Historico_danos.route('/exportar_excel')
@login_required
@requiere_permiso('Ingresar_historico_danos')
def exportar_excel():

    es_exportacion_laboral = request.args.get('modulo') == 'laboral'
    if es_exportacion_laboral and 'Ingresar_modulo__laboral' not in session.get('permisos', []):
        abort(403)

    try:
        fecha_inicio, fecha_fin = _leer_fechas()
    except FiltroInvalido as error:
        return str(error), 400

    filtro_uf = request.args.get('filtro_uf', 'todos')
    # Solo RRLL usa filtro_estado (pendientes / gestionados / cerrados).
    filtro_estado = request.args.get('filtro_estado', 'todos')

    estados = []
    if not es_exportacion_laboral:
        estados = [e for e in _leer_estados() if e != 'eliminados']
        if not estados:
            return "Los casos eliminados no se incluyen en el Excel. Seleccione Abiertos o Cerrados.", 400

    where_sql, parametros = modelo_exportacion.filtro_de_la_exportacion(
        ufs_autorizadas_sesion(), fecha_inicio, fecha_fin, filtro_uf, estados, es_exportacion_laboral)

    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
        registros, laboral_por_caso = modelo_exportacion.listar_para_exportar(
            cursor, where_sql, parametros, es_exportacion_laboral)

    if es_exportacion_laboral:
        for registro in registros:
            registro["estado_excel"] = estado_rrll_para_exportacion(registro)

        estado_por_filtro = {
            "pendientes": "PENDIENTE",
            "gestionados": "GESTIONADO",
            "comite": "COMITE",
            "cerrados": "CERRADO",
        }
        estado_solicitado = estado_por_filtro.get(filtro_estado)
        if estado_solicitado:
            registros = [
                registro for registro in registros
                if registro["estado_excel"] == estado_solicitado
            ]

    output = crear_excel_historico(registros, laboral_por_caso, es_exportacion_laboral)

    return send_file(
        output,
        download_name="Historico_Danos.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
