"""Ruta genérica "/<modulo>/<accion>" (POST) que registra la gestión de cada módulo.

Valida lo común (permiso del módulo, caso de la UF y abierto, adjuntos) y reparte:
Operaciones y RRLL tienen controlador propio; Mantenimiento y Seguridad Vial
comparten el flujo de guardar_gestion() con su parte propia en su controlador.
"""
from repositories.sesiones import sesion_bd
from contextlib import closing
from datetime import datetime

from flask import abort, jsonify, request

import backend_unificado as fachada
from backend_security import usuario_id_sesion
from backend_security import login_required
from config import UPLOAD_FOLDERS
from logger import logger
from modelos import auditoria as modelo_auditoria
from servicios.flujo_caso import cerrar_caso_automaticamente
from unificado import laboral, mantenimiento, operaciones, seguridad_vial
from unificado.archivos import borrar_archivos, guardar_archivos
from unificado.comun import leer_valor_monetario, validar_adjuntos_de_solicitud, verificar_acceso_modulo
from unificado.configuracion import CONFIG_GESTIONES

# Parte propia de cada módulo dentro del flujo común.
REGISTRAR_GESTION = {
    "Mtto": mantenimiento.registrar_gestion,
    "Svial": seguridad_vial.registrar_gestion,
}

CAMPOS_MONETARIOS = {"Costo": "El costo", "valor_conciliado_terceros": "El valor conciliado"}


@fachada.Modulo_unificado.route("/<modulo>/<accion>", methods=["POST"])
@login_required
def agregar(modulo, accion):

    verificar_acceso_modulo(modulo)
    # Toda gestión se registra sobre un caso existente, de la UF del usuario y abierto.
    id_registro_solicitado = request.form.get("Id_damage_to_fleet")
    if not id_registro_solicitado:
        return jsonify({"status": "error", "message": "Falta el identificador del registro."}), 400
    fachada.verificar_acceso_uf_caso(id_registro_solicitado, exigir_abierto=True)
    error_adjuntos = validar_adjuntos_de_solicitud()
    if error_adjuntos:
        return error_adjuntos

    if modulo == "laboral" and accion == "agregar_rl":
        return laboral.agregar_relaciones_laborales()

    if modulo == "Operaciones" and accion == "agregar_oper":
        return operaciones.agregar_operaciones()

    if modulo not in CONFIG_GESTIONES:
        abort(404)

    ICFG = CONFIG_GESTIONES[modulo]

    if accion != ICFG["ruta"]:
        abort(404)

    return guardar_gestion(modulo, ICFG)


def leer_valores_de_gestion(ICFG, id_registro, usuario):
    """Valores en el orden de ICFG["campos"]. ValueError si un valor en pesos no es válido."""
    valores = []
    for campo in ICFG["campos"]:
        origen = campo["origen"]
        if origen == "id":
            valores.append(id_registro)
        elif origen == "usuario":
            valores.append(usuario)
        else:
            valor = request.form.get(origen)
            if origen in CAMPOS_MONETARIOS:
                valor = leer_valor_monetario(
                    valor, CAMPOS_MONETARIOS[origen], obligatorio=(origen == "Costo")
                )
            valores.append(valor)
    return valores


def crear_auditor(cursor, id_registro, usuario, motivo_modificacion):
    """Función que deja en la auditoría cada campo que cambió, si hay motivo."""
    def auditar_cambio(tabla, campo, anterior, nuevo):
        if not motivo_modificacion or str(anterior if anterior is not None else "") == str(nuevo if nuevo is not None else ""):
            return
        modelo_auditoria.registrar_correccion(
            cursor, id_registro, tabla, campo, str(anterior or ""), str(nuevo or ""),
            usuario, datetime.now(), motivo_modificacion)
    return auditar_cambio


def guardar_gestion(modulo, ICFG):
    """Flujo común de Mantenimiento y Seguridad Vial: gestión, adjuntos y cierre
    automático en un solo commit."""
    id_registro = request.form.get("Id_damage_to_fleet")
    usuario = usuario_id_sesion()  # nunca el campo del formulario

    if not id_registro:
        return jsonify({"status": "error", "message": "Falta el identificador del registro."}), 400

    try:
        valores = leer_valores_de_gestion(ICFG, id_registro, usuario)
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400

    rutas_guardadas = []
    # closing() cierra cursor y conexión siempre; el rollback ocurre antes, en el except.
    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        motivo_modificacion = (request.form.get("Motivo_modificacion") or "").strip()
        auditar_cambio = crear_auditor(cursor, id_registro, usuario, motivo_modificacion)
        try:
            REGISTRAR_GESTION[modulo](cursor, id_registro, valores, auditar_cambio)
            guardar_archivos(cursor, id_registro, UPLOAD_FOLDERS[modulo],
                             rutas_guardadas)
            cerrar_caso_automaticamente(cursor, id_registro, usuario)
            conn.commit()
        except Exception:
            conn.rollback()
            borrar_archivos(rutas_guardadas)
            logger.exception("error_operacion_modulo")
            return jsonify({
                "status": "error",
                "message": "No fue posible completar la operación."
            }), 500

        respuesta = {"status": "success", "message": "Registro guardado correctamente."}
        if modulo == "Mtto":
            respuesta.update(mantenimiento.estado_tras_guardar(cursor, id_registro))
    return jsonify(respuesta)
