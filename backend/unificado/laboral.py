"""Relaciones Laborales: seguimiento del caso, procesos pendientes y cierre (con auditoría).

La ruta es la genérica "/laboral/agregar_rl" de gestiones.py, que ya validó el
permiso, la UF y que el caso esté abierto.
"""
from conexiones import transaccion
from repositories.sesiones import sesion_bd
from contextlib import closing
from datetime import datetime

from flask import jsonify, request

from backend_security import usuario_id_sesion
import backend_unificado as fachada
from config import UPLOAD_FOLDERS
from logger import logger
from modelos import auditoria as modelo_auditoria
from modelos import casos as modelo_casos
from modelos import laboral as modelo_laboral
from servicios.flujo_caso import normalizar_procesos_pendientes
from unificado.archivos import borrar_archivos, guardar_archivos
from unificado.comun import leer_valor_monetario


# ==========================================================
# INSERT RELACIONES LABORALES (upsert + auditoría)
# ==========================================================

def agregar_relaciones_laborales():
    rutas_guardadas = []
    try:
        codigo = request.form.get("Id_damage_to_fleet")
        observaciones_1 = request.form.get("observaciones_1")
        usuario = usuario_id_sesion()  # nunca el campo del formulario
        fecha_presentacion = request.form.get("Fecha_presentacion_input")
        try:
            pendiente_proceso, procesos_pendientes = normalizar_procesos_pendientes(
                request.form.get("Estado_caso")
            )
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400
        motivo_modificacion = (request.form.get("Motivo_modificacion") or "").strip()

        rev_inf = request.form.get("Revinf", "NO")
        tipo_cerrado = request.form.get("Tipo_cerrado_input", "")
        try:
            costo = leer_valor_monetario(request.form.get("Costo"), "El valor conciliado")
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        if not codigo or not observaciones_1 or not usuario:
            return jsonify({"status": "error", "message": "Faltan datos obligatorios."}), 400

        # El helper revierte antes de cerrar y conserva el error para la respuesta.
        with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
            with transaccion(conn):
                modelo_laboral.registrar_seguimiento(
                    cursor, codigo, fecha_presentacion, pendiente_proceso, observaciones_1,
                    usuario, datetime.now())

                # Un caso puede quedar pendiente por varios procesos. Solo se
                # restablecen los estados de los módulos expresamente seleccionados;
                # COMPLETO equivale a todo bien
                for proceso in modelo_laboral.GESTION_POR_PROCESO:
                    if proceso in procesos_pendientes:
                        modelo_laboral.devolver_proceso_a_pendiente(cursor, proceso, codigo)

                if rev_inf == "SI":
                    registrar_cierre(cursor, codigo, tipo_cerrado, costo, usuario, motivo_modificacion)

                guardar_archivos(cursor, codigo, UPLOAD_FOLDERS["laboral"],
                                 rutas_guardadas)

        return jsonify({"status": "success", "message": "✅ Información de RRLL y archivos guardados correctamente."})

    except Exception:
        borrar_archivos(rutas_guardadas)
        logger.exception("error_guardar_relaciones_laborales")
        return jsonify({"status": "error", "message": "No fue posible guardar la información de Relaciones Laborales."}), 500


def registrar_cierre(cursor, codigo, tipo_cerrado, costo, usuario, motivo_modificacion):
    """Crea o corrige el cierre de RRLL (auditando cada cambio) y, si hay tipo de
    cierre, cierra el caso."""
    registro_existente = modelo_laboral.buscar_cierre(cursor, codigo)

    if registro_existente:
        campos = {
            "tipo_cierre": (registro_existente[0], tipo_cerrado),
            "valor_conciliado": (str(registro_existente[1]), str(costo))
        }

        hubo_cambio = False
        for campo, valores in campos.items():
            valor_anterior, valor_nuevo = valores
            if str(valor_nuevo) != str(valor_anterior):
                hubo_cambio = True
                modelo_auditoria.registrar_correccion(
                    cursor, codigo, modelo_laboral.TABLA_CIERRE, campo, str(valor_anterior), str(valor_nuevo),
                    usuario, datetime.now(), motivo_modificacion)

        if hubo_cambio:
            modelo_laboral.actualizar_cierre(cursor, codigo, tipo_cerrado, costo, usuario)
    else:
        modelo_laboral.crear_cierre(cursor, codigo, tipo_cerrado, costo, usuario)

    # En Relaciones Laborales, el tipo de cierre confirma que esta es la
    # gestión final del caso.
    if tipo_cerrado:
        modelo_casos.marcar_caso_cerrado(cursor, codigo)
