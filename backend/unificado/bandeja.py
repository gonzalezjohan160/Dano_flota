"""Bandeja de cada módulo (tabla principal con sus casos) y lista de móviles."""
from repositories.sesiones import sesion_bd
from contextlib import closing
from datetime import datetime

from flask import abort, jsonify, render_template

import backend_unificado as fachada
from backend_security import login_required, ufs_autorizadas_sesion
from modelos import bandeja as modelo_bandeja
from modelos import catalogos as modelo_catalogos
from servicios.flujo_caso import requiere_relaciones_laborales, caso_en_comite
from unificado.comun import config_publica_modulo, verificar_acceso_modulo
from unificado.configuracion import MODULOS


# ==========================================================
# PANTALLA PRINCIPAL — TABLA CON TODOS LOS REGISTROS
# ==========================================================

@fachada.Modulo_unificado.route("/<modulo>")
@login_required
def index(modulo):

    verificar_acceso_modulo(modulo)

    CFG = MODULOS[modulo]

    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        registros = modelo_bandeja.listar_casos_del_modulo(cursor, ufs_autorizadas_sesion(), modulo)
        # Solo Operaciones edita el evento y necesita las listas de los catálogos.
        catalogos = (
            modelo_catalogos.listas_para_el_navegador(modelo_catalogos.cargar_listas_del_caso(cursor))
            if modulo == "Operaciones" else {}
        )

    for r in registros:

        fecha = r.get("Fecha_evento")
        r["fecha"] = fecha.strftime("%Y-%m-%dT%H:%M") if fecha else None
        del r["Fecha_evento"]

        fecha_r = r.get("Fecha_registro")
        if isinstance(fecha_r, datetime):
            r["fecha_r"] = fecha_r.strftime("%d/%m/%Y %H:%M:%S")
        else:
            r["fecha_r"] = None
        del r["Fecha_registro"]

        r["tiene_oper"] = bool(r["tiene_oper"])
        r["tiene_mtto"] = bool(r["tiene_mtto"])
        r["tiene_svial"] = bool(r["tiene_svial"])
        r["tiene_laboral"] = bool(r["tiene_laboral"])
        r["tiene_ot"] = bool(r["tiene_ot"])
        r["requiere_laboral"] = r["tiene_oper"] and requiere_relaciones_laborales(
            r.pop("responsabilidad_operador"), r.pop("conciliacion")
        )

        r["pendiente_ot"] = (r["requiere_laboral"] and r["tiene_mtto"]
        and (not r["estado_mtto"] or not r["tiene_ot"]))

        r["caso_cerrado"] = bool(r["caso_cerrado"])
        r["en_comite"] = caso_en_comite(r.get("pendiente_proceso_actual"), r["caso_cerrado"])
        r["cerrado_por_laboral"] = bool(r["cerrado_por_laboral"])
        campo_estado = {"Operaciones": "estado_oper", "Mtto": "estado_mtto", "Svial": "estado_svial"}.get(modulo)
        r["estado_modulo"] = bool(r[campo_estado]) if campo_estado else None

        fecha_rl = r.get("Fecha_r_laboral")
        if isinstance(fecha_rl, datetime):
            r["fecha_r_laboral"] = fecha_rl.strftime("%d/%m/%Y %H:%M:%S")
        else:
            r["fecha_r_laboral"] = None
        del r["Fecha_r_laboral"]

    if modulo == "laboral":
        registros = [
            r for r in registros
            if not (
                r["estado_oper"] == 1 and r["estado_mtto"] == 1 and r["estado_svial"] == 1
                and r["requiere_laboral"] and not r["tiene_ot"] and not r["en_comite"]
            )
        ]

    return render_template(
        "Modulo_unificado.html",
        registros=registros,
        titulo_modulo=CFG["titulo"],
        tipo_modulo=CFG["tipo"],
        modulo=modulo,
        modulo_config=config_publica_modulo(modulo),
        catalogos_evento=catalogos,
    )


@fachada.Modulo_unificado.route("/<modulo>/opciones_evento")
@login_required
def opciones_evento(modulo):
    verificar_acceso_modulo(modulo)
    if modulo not in ("Operaciones", "Mtto", "Svial"):
        abort(404)
    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        ufs = ufs_autorizadas_sesion()
        if not ufs:
            return jsonify({"moviles": []})
        return jsonify({"moviles": modelo_bandeja.listar_moviles(cursor, ufs)})
