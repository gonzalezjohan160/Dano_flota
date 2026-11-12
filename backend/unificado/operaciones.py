"""Operaciones: reincidencia del operador y registro de la gestión de Operaciones
(valor del daño / responsabilidad / conciliación)."""
from conexiones import transaccion
from repositories.sesiones import sesion_bd
from contextlib import closing
from datetime import datetime

from flask import jsonify, request

from backend_security import usuario_id_sesion
from modelos import usuarios as modelo_usuarios
import backend_unificado as fachada
from backend_security import login_required
from config import UPLOAD_FOLDERS
from logger import logger
from modelos import auditoria as modelo_auditoria
from modelos import casos as modelo_casos
from modelos import operaciones as modelo_operaciones
from servicios.flujo_caso import cerrar_caso_automaticamente
from unificado.archivos import borrar_archivos, guardar_archivos
from unificado.comun import leer_valor_monetario, verificar_acceso_modulo


# ==========================================================
# VERIFICAR REINCIDENCIA DEL OPERADOR (últimos 2 meses)
# ==========================================================
#
# Se consulta desde el formulario de Operaciones cuando la
# responsabilidad del operador es SI o NO (ambas cuentan como
# responsabilidad del operador; "NO APLICA" nunca llama a este
# endpoint), tal como pide el requerimiento.
#
# NOTA: la resta de 2 meses está escrita para SQL Server (DATEADD) en
# modelos/operaciones.py; el resto de la lógica no depende del motor.

def obtener_reincidencia_operador(cursor, id_dano):
    """Cuenta los antecedentes únicos e incluye el evento actual."""
    fila = modelo_operaciones.buscar_operador_y_fecha_del_caso(cursor, id_dano)

    if not fila or not fila[0] or not fila[1]:
        return 0

    codigo_operador, fecha_evento_actual = fila

    if str(codigo_operador).strip() in ("1", "2", "3", "4", "5", "6", "7"):
        return 0

    antecedentes = modelo_operaciones.contar_antecedentes_con_responsabilidad(
        cursor, codigo_operador, id_dano, fecha_evento_actual)

    # El evento actual se cuenta una vez, incluso antes de guardarse.
    return antecedentes + 1


@fachada.Modulo_unificado.route("/Operaciones/verificar_reincidencia/<int:id>")
@login_required
def verificar_reincidencia_operador(id):

    verificar_acceso_modulo("Operaciones")
    fachada.verificar_acceso_uf_caso(id)

    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        total = obtener_reincidencia_operador(cursor, id)

    return jsonify({"eventos": total, "bloqueado": total >= 3})


# ==========================================================
# INSERT OPERACIONES (flujo nuevo: valor del daño / responsabilidad /
# conciliación)
# ==========================================================
#
# Operaciones tiene controlador propio (no usa CONFIG_GESTIONES) porque su
# formulario tiene inserts condicionales que el flujo genérico de
# gestiones.py no soporta. La ruta "/Operaciones/agregar_oper" llega aquí
# desde gestiones.agregar.

def agregar_operaciones():
    rutas_guardadas = []
    try:
        codigo = request.form.get("Id_damage_to_fleet")
        observaciones_1 = request.form.get("observaciones_1")
        usuario = usuario_id_sesion()  # nunca el campo del formulario
        motivo_modificacion = (request.form.get("Motivo_modificacion") or "").strip()

        # Pregunta 1: ¿el costo del daño supera $2.000.000?
        costo_supera_2m = request.form.get("costo_supera_2m")  # "SI" / "NO"
        costo_valor = request.form.get("costo_valor")          # solo si NO

        # Solo aplica cuando el costo NO supera los $2.000.000
        responsabilidad_operador = request.form.get("responsabilidad_operador")  # SI / NO / NO APLICA
        conciliacion = request.form.get("conciliacion")  # SI / NO (solo si responsabilidad = SI y no hay reincidencia)
        valor_conciliado_oper = request.form.get("valor_conciliado_oper")  # solo si conciliacion = SI
        motivo_cierre_oper = request.form.get("motivo_cierre_oper", "")
        # Se validan antes de abrir la conexión: un valor inválido responde 400.
        try:
            costo_valor = leer_valor_monetario(costo_valor, "El costo del daño")
            valor_conciliado_oper = leer_valor_monetario(valor_conciliado_oper, "El valor conciliado")
        except ValueError as error:
            return jsonify({"status": "error", "message": str(error)}), 400

        if not codigo or not observaciones_1 or not usuario:
            return jsonify({"status": "error", "message": "Faltan datos obligatorios."}), 400

        if costo_supera_2m not in ("SI", "NO"):
            return jsonify({"status": "error", "message": "Indique si el costo supera los $2.000.000."}), 400

        no_supera = costo_supera_2m == "NO"
        if no_supera and responsabilidad_operador not in ("SI", "NO", "NO APLICA"):
            return jsonify({"status": "error", "message": "Seleccione Sí, No o No aplica para la responsabilidad del operador."}), 400

        if no_supera and responsabilidad_operador == "NO APLICA":
            conciliacion = None
            if motivo_cierre_oper not in ("RETIRO", "EXONERACIÓN"):
                return jsonify({"status": "error", "message": "Completa este campo"}), 400

        # El helper revierte antes de cerrar y conserva el error para la respuesta.
        with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
            bloqueado_reincidencia = (
                no_supera
                and responsabilidad_operador in ("SI", "NO")
                and obtener_reincidencia_operador(cursor, codigo) >= 3
            )

            # La regla se valida nuevamente en el servidor. Aunque el cliente
            # envíe conciliación, un tercer evento no puede terminar allí.
            if bloqueado_reincidencia:
                conciliacion = None

            # La misma gestión puede reenviarse antes de recibir respuesta del
            # navegador. El bloqueo se conserva hasta el commit para que solo
            # exista un registro de Operaciones por cada daño.
            registro_oper_anterior = modelo_operaciones.bloquear_gestion_anterior(cursor, codigo)

            if registro_oper_anterior and not motivo_modificacion:
                return jsonify({
                    "status": "error",
                    "message": "El motivo del cambio es obligatorio."
                }), 400

            with transaccion(conn):
                valores_oper = (
                    observaciones_1,
                    usuario,
                    responsabilidad_operador if no_supera else None,
                    conciliacion if (no_supera and responsabilidad_operador == "SI") else None,
                    costo_valor if no_supera else None
                )

                if registro_oper_anterior:
                    if motivo_modificacion:
                        for campo, anterior, nuevo in zip(
                            modelo_operaciones.COLUMNAS_DE_LA_GESTION.values(),
                            registro_oper_anterior, valores_oper
                        ):
                            if str(anterior if anterior is not None else "") != str(nuevo if nuevo is not None else ""):
                                if campo == "Usuario_registro_oper":
                                    anterior = modelo_usuarios.buscar_nombre_por_id(cursor, anterior) if anterior else None
                                    nuevo = modelo_usuarios.buscar_nombre_por_id(cursor, nuevo) if nuevo else None
                                modelo_auditoria.registrar_correccion(
                                    cursor, codigo, modelo_operaciones.TABLA_GESTION, campo, str(anterior or ""),
                                    str(nuevo or ""), usuario, datetime.now(), motivo_modificacion)
                    modelo_operaciones.actualizar_gestion(cursor, codigo, valores_oper)
                else:
                    modelo_operaciones.crear_gestion(cursor, codigo, valores_oper)

                # Si hubo conciliación, o si el operador respondió "NO APLICA"
                # (mismo tratamiento: el caso termina en Operaciones), el valor
                # se guarda reutilizando exactamente la misma columna que usa
                # Relaciones Laborales (proceso.table_info_labora.valor_conciliado), tal
                # como pide el requerimiento -- no se crea una columna nueva.
                termina_en_operaciones = not bloqueado_reincidencia and no_supera and (
                    (responsabilidad_operador == "SI" and conciliacion == "SI")
                    or responsabilidad_operador == "NO APLICA"
                )

                if responsabilidad_operador == "NO APLICA":
                    tipo_cerrado = motivo_cierre_oper
                else:
                    tipo_cerrado = "CONCILIACIÓN"

                if termina_en_operaciones:
                    if modelo_operaciones.existe_registro_laboral(cursor, codigo):
                        modelo_operaciones.actualizar_cierre_laboral(
                            cursor, codigo, valor_conciliado_oper, tipo_cerrado)
                    else:
                        modelo_operaciones.crear_cierre_laboral(
                            cursor, codigo, tipo_cerrado, valor_conciliado_oper, usuario)

                guardar_archivos(cursor, codigo, UPLOAD_FOLDERS["Operaciones"],
                                 rutas_guardadas)

                if termina_en_operaciones:
                    cerrar_caso_automaticamente(cursor, codigo, usuario)
                else:
                    # Al reabrir y modificar Operaciones, una decisión nueva que
                    # requiere RRLL no puede reutilizar un cierre histórico de
                    # proceso.table_info_labora. Si ese registro provino de un cierre previo
                    # de Operaciones (sin historial en RRLL), se retira para que el
                    # caso ingrese como pendiente; la eliminación queda auditada.
                    cierre_operaciones_anterior = modelo_operaciones.buscar_cierre_previo_de_operaciones(
                        cursor, codigo)
                    if cierre_operaciones_anterior:
                        modelo_auditoria.registrar_correccion(
                            cursor, codigo, modelo_operaciones.TABLA_CIERRE, "Cierre previo de Operaciones",
                            f"Tipo: {cierre_operaciones_anterior[0] or ''}; Valor: {cierre_operaciones_anterior[1] or ''}",
                            "", usuario, datetime.now(), motivo_modificacion
                        )
                        modelo_operaciones.retirar_cierre_laboral(cursor, codigo)

                    # Se preservan los demás registros; solo se mantiene abierto el
                    # caso para que el filtro vigente de RRLL evalúe los datos nuevos.
                    modelo_casos.marcar_caso_abierto(cursor, codigo)
                    cerrar_caso_automaticamente(cursor, codigo, usuario, permitir_cierre=False)


        return jsonify({
            "status": "success",
            "message": "Registro guardado correctamente.",
            "bloqueado_reincidencia": bloqueado_reincidencia
        })

    except Exception:
        borrar_archivos(rutas_guardadas)
        logger.exception("error_guardar_operaciones")
        return jsonify({"status": "error", "message": "No fue posible guardar la información de Operaciones."}), 500
