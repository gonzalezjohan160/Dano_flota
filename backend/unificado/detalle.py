"""Detalle cruzado de un caso: datos del evento, gestiones, historial de RRLL y adjuntos."""
from repositories.sesiones import sesion_bd
from contextlib import closing

from flask import jsonify

import backend_unificado as fachada
from backend_security import login_required, puede_ver_adjuntos_laborales
from modelos import detalle_caso as modelo_detalle
from servicios.flujo_caso import evento_pendiente_para_modulo
from unificado.comun import verificar_acceso_modulo


# ==========================================================
# DETALLE DE UN REGISTRO
# ==========================================================

@fachada.Modulo_unificado.route("/<modulo>/detalle/<int:id>")
@login_required
def detalle(modulo, id):

    verificar_acceso_modulo(modulo)
    fachada.verificar_acceso_uf_caso(id)

    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        consulta = modelo_detalle.buscar_detalle_del_caso(cursor, id)

    detalle_principal = consulta["principal"]

    registro = {
        campo: detalle_principal.get(campo)
        for campo in (
            "UF", "Movil", "Codigo", "Nombre", "Area", "Ruta", "Tipologia", "Version_libre",
            "Zona_dano", "Parte_afectada", "Dano_ocasionado",
            "Centro_operaciones", "Registrador", "Direccion"
        )
    }
    oper = {
        campo: detalle_principal.get(campo)
        for campo in (
            "Observaciones_operaciones", "rev_error", "Observaciones_correctivos",
            "responsabilidad_operador",
            "conciliacion", "CostoDelDanoOper", "ValorConciliadoOper"
        )
    }
    mtto = {
        "Costo": detalle_principal.get("CostoMtto"),
        "observaciones": detalle_principal.get("observaciones_mtto"),
        "dano_adicional": detalle_principal.get("dano_adicional")
    }
    svial = {"Observaciones_svial": detalle_principal.get("Observaciones_svial")}
    laboral_estado = {
        "Tipo_cerrado": detalle_principal.get("Tipo_cerrado"),
        "Valor_conciliado": detalle_principal.get("Valor_conciliado_laboral")
    }

    laboral_eventos = consulta["eventos_laborales"]
    laboral_pendientes = [
        evento for evento in laboral_eventos
        if evento_pendiente_para_modulo(evento, modulo)
    ]

    archivos = consulta["archivos"]
    archivos_mtto = consulta["archivos_mtto"]
    archivos_svial = consulta["archivos_svial"]
    archivos_laboral = consulta["archivos_laboral"]
    # Fuera de RRLL no se listan, para que la galería no muestre archivos que no abren.
    if not puede_ver_adjuntos_laborales():
        archivos_laboral = []

    respuesta = {
        "registro": registro,
        "oper": oper,
        "mtto": mtto,
        "svial": svial,
        "laboral": {
            "eventos": laboral_eventos,
            "estado": laboral_estado,
            "pendientes": laboral_pendientes,
        },
        "archivos": archivos,
        "archivos_mtto": archivos_mtto,
        "archivos_svial": archivos_svial,
        "archivos_laboral": archivos_laboral
    }


    respuesta_json = jsonify(respuesta)

    return respuesta_json
