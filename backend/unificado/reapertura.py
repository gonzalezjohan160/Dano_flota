"""Reapertura de un caso cerrado, desde Operaciones o desde Relaciones Laborales.

Reabrir no altera las gestiones ya registradas; solo cambia el estado del caso y
deja la auditoría con el motivo.
"""
from repositories.sesiones import sesion_bd
from contextlib import closing
from datetime import datetime

from flask import jsonify, request

from backend_security import usuario_id_sesion
import backend_unificado as fachada
from backend_security import login_required, requiere_permiso, usuario_puede_acceder_uf
from logger import logger
from modelos import auditoria as modelo_auditoria
from modelos import casos as modelo_casos
from unificado.comun import verificar_acceso_modulo


def reabrir_caso(id, modulo):
    """Reabre un caso cerrado sin alterar las gestiones ya registradas."""
    verificar_acceso_modulo(modulo)
    datos = request.get_json(silent=True) or {}
    motivo = (datos.get("motivo_modificacion") or "").strip()
    if not motivo:
        return jsonify({"status": "error", "message": "El motivo de reapertura es obligatorio."}), 400

    # closing() cierra cursor y conexión siempre; el rollback ocurre antes, en el except.
    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        try:
            caso = modelo_casos.buscar_estado_para_reabrir(cursor, id, desde_laboral=modulo == "laboral")
            if not caso:
                return jsonify({"status": "error", "message": "No se encontró el evento."}), 404
            if not usuario_puede_acceder_uf(caso[0]):
                return jsonify({"status": "error", "message": "No tiene acceso a este caso."}), 403
            if not caso[1]:
                return jsonify({"status": "error", "message": "El caso ya se encuentra abierto."}), 409
            if modulo == "laboral" and not caso[2]:
                return jsonify({"status": "error", "message": "El caso no fue cerrado por Relaciones Laborales."}), 409

            usuario = usuario_id_sesion()
            modelo_casos.marcar_caso_abierto(cursor, id)
            modelo_auditoria.registrar_correccion(
                cursor, id, "flota.table_damage_to_fleet", "estado_caso", "1", "0",
                usuario, datetime.now(), motivo)
            conn.commit()
            return jsonify({"status": "success", "message": "Caso reabierto correctamente."})
        except Exception:
            conn.rollback()
            logger.exception("error_reabrir_evento")
            return jsonify({"status": "error", "message": "No fue posible reabrir el evento."}), 500


@fachada.Modulo_unificado.route("/Operaciones/reabrir_evento/<int:id>", methods=["POST"])
@login_required
@requiere_permiso("Reabrir_caso_oper")
def reabrir_evento(id):
    return reabrir_caso(id, "Operaciones")


@fachada.Modulo_unificado.route("/laboral/reabrir_evento/<int:id>", methods=["POST"])
@login_required
@requiere_permiso("Reabrir_caso_rr_ll")
def reabrir_evento_laboral(id):
    return reabrir_caso(id, "laboral")
