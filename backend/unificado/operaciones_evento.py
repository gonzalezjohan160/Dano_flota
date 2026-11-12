"""Operaciones: editar la información del evento, consultar el operador y
eliminar el caso (borrado lógico con auditoría)."""
from repositories.sesiones import sesion_bd
from contextlib import closing
from datetime import datetime
import json

from flask import abort, jsonify, request

from backend_security import usuario_id_sesion
import backend_unificado as fachada
from backend_security import login_required, requiere_permiso, usuario_puede_acceder_uf
from config import UPLOAD_FOLDERS
from logger import logger
from modelos import auditoria as modelo_auditoria
from modelos import catalogos as modelo_catalogos
from modelos import flota as modelo_flota
from modelos import operaciones as modelo_operaciones
from servicios.validacion_caso import area_del_operador, error_de_catalogo, prefijo_movil_de_la_uf
from servicios.edicion_imagenes import validar_ids_imagenes, preparar_eliminacion, eliminar_en_transaccion
from unificado.archivos import borrar_archivos, guardar_archivos
from unificado.comun import validar_adjuntos_de_solicitud, verificar_acceso_modulo


@fachada.Modulo_unificado.route("/<modulo>/actualizar_evento/<int:id>", methods=["POST"])
@login_required
@requiere_permiso("Corregir_info_oper")
def actualizar_evento(modulo, id):
    verificar_acceso_modulo(modulo)
    if modulo != "Operaciones":
        abort(404)
    fachada.verificar_acceso_uf_caso(id, exigir_abierto=True)
    error_adjuntos = validar_adjuntos_de_solicitud()
    if error_adjuntos:
        return error_adjuntos

    datos = request.get_json(silent=True) or {}
    if not datos:
        try:
            datos = {
                "evento": json.loads(request.form.get("evento", "{}")),
                "motivo_modificacion": request.form.get("motivo_modificacion", ""),
                "archivos_eliminar": json.loads(request.form.get("archivos_eliminar", "[]"))
            }
        except json.JSONDecodeError:
            return jsonify({"status": "error", "message": "Los datos del evento no son válidos."}), 400
    if not isinstance(datos, dict) or not isinstance(datos.get("evento", {}), dict):
        return jsonify({"status": "error", "message": "Los datos del evento no son válidos."}), 400
    if not isinstance(datos.get("motivo_modificacion", ""), str):
        return jsonify({"status": "error", "message": "El motivo del cambio no es válido."}), 400
    cambios = datos.get("evento") or {}
    motivo = (datos.get("motivo_modificacion") or "").strip()
    if not motivo:
        return jsonify({"status": "error", "message": "El motivo del cambio es obligatorio."}), 400
    try:
        ids_eliminar = validar_ids_imagenes(datos.get("archivos_eliminar", []))
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400

    # La UF solo se usa para validar el móvil; la tipología la pone el móvil.
    campos_permitidos = set(modelo_operaciones.CAMPOS_EDITABLES_DEL_CASO) | {"UF", "Tipologia"}
    cambios = {campo: valor for campo, valor in cambios.items() if campo in campos_permitidos}
    tiene_archivos = any(archivo.filename for archivo in request.files.getlist("archivos"))
    if not cambios and not tiene_archivos and not ids_eliminar:
        return jsonify({"status": "success", "message": "No hay cambios para guardar."})

    rutas_guardadas = []
    # closing() cierra cursor y conexión siempre; el rollback ocurre antes, en el except.
    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        try:
            actual = modelo_operaciones.buscar_caso_completo(cursor, id)
            if not actual:
                return jsonify({"status": "error", "message": "No se encontró el evento."}), 404
            if not usuario_puede_acceder_uf(actual.get("UF")):
                return jsonify({"status": "error", "message": "No tiene acceso a este caso."}), 403
            try:
                imagenes_eliminar = preparar_eliminacion(cursor, id, ids_eliminar)
            except ValueError as error:
                return jsonify({"status": "error", "message": str(error)}), 400

            # La fecha del evento no puede quedar después de la fecha en que se registró el caso.
            if "Fecha_evento" in cambios:
                try:
                    nueva_fecha_evento = datetime.strptime(str(cambios["Fecha_evento"]), "%Y-%m-%dT%H:%M")
                except ValueError:
                    return jsonify({"status": "error", "message": "La fecha del evento no es válida."}), 400
                fecha_registro = actual.get("Fecha_registro")
                if fecha_registro and nueva_fecha_evento > fecha_registro:
                    return jsonify({"status": "error", "message": (
                        "La fecha del evento no puede ser posterior a la fecha en que se registró el caso "
                        f"({fecha_registro:%d/%m/%Y %H:%M}). Revise el día y si la hora es AM o PM."
                    )}), 400

            # La UI calcula estos valores, pero se validan y recalculan también
            # en el servidor para impedir guardar datos incoherentes. Las listas
            # son las mismas del capturador (catálogos de la base).
            listas = modelo_catalogos.cargar_listas_del_caso(cursor)
            uf = str(cambios.pop("UF", actual.get("UF") or "")).strip()
            cambios.pop("Tipologia", None)  # la tipología es la del móvil
            movil = str(cambios.get("Movil", actual.get("Movil") or "")).strip().upper()
            prefijo = prefijo_movil_de_la_uf(listas, uf)
            if prefijo is None:
                return jsonify({"status": "error", "message": "La UF no es válida."}), 400
            if not usuario_puede_acceder_uf(uf):
                return jsonify({"status": "error", "message": "No tiene autorización para asignar esa UF."}), 403
            if not movil.startswith(prefijo) or not movil[len(prefijo):].isdigit() or len(movil[len(prefijo):]) != 4:
                return jsonify({"status": "error", "message": "El móvil debe conservar el prefijo de la UF y cuatro dígitos."}), 400
            if not modelo_flota.movil_pertenece_a_uf(cursor, movil, uf):
                return jsonify({"status": "error", "message": "El móvil no está registrado en esa UF."}), 400
            cambios["Movil"] = movil

            codigo = str(cambios.get("Codigo", actual.get("Codigo") or "")).strip()
            cambios["Codigo"] = codigo
            cambios["Area"] = area_del_operador(listas, codigo)
            if codigo not in listas["areas_por_codigo"]:
                conductor = modelo_operaciones.buscar_nombre_del_operador(cursor, codigo)
                if conductor:
                    cambios["Nombre"] = conductor[0]

            centro = str(cambios.get("Centro_operaciones", actual.get("Centro_operaciones") or "")).strip().upper()
            error = error_de_catalogo(listas, centro_operacion=centro)
            if error:
                return jsonify({"status": "error", "message": error}), 400
            cambios["Centro_operaciones"] = centro

            # La ruta debe ser de la UF del móvil. La zona y la causa solo se exigen
            # si el valor cambia, para no bloquear la edición de registros antiguos
            # (sus valores históricos siguen en el catálogo, inactivos).
            if "Ruta" in cambios:
                ruta = str(cambios["Ruta"] or "").strip()
                if ruta != str(actual.get("Ruta") or "").strip() or uf != str(actual.get("UF") or ""):
                    error = error_de_catalogo(listas, uf=uf, ruta=ruta)
                    if error:
                        return jsonify({"status": "error", "message": error}), 400
                cambios["Ruta"] = ruta
            for campo, clave in (("Zona_dano", "zona_dano"), ("Dano_ocasionado", "tipo_dano")):
                if campo in cambios:
                    valor = str(cambios[campo] or "").strip()
                    if valor != str(actual.get(campo) or "").strip():
                        error = error_de_catalogo(listas, **{clave: valor})
                        if error:
                            return jsonify({"status": "error", "message": error}), 400
                    cambios[campo] = valor
            if "Parte_afectada" in cambios:
                parte = str(cambios["Parte_afectada"] or "").strip()
                if not parte or len(parte) > 200:
                    return jsonify({"status": "error", "message": "La parte afectada es obligatoria y no puede superar 200 caracteres."}), 400
                cambios["Parte_afectada"] = parte

            def valor_comparable(campo, valor):
                if campo == "Fecha_evento" and isinstance(valor, datetime):
                    return valor.strftime("%Y-%m-%d")
                return str(valor if valor is not None else "")

            cambios_reales = {
                campo: valor for campo, valor in cambios.items()
                if valor_comparable(campo, actual.get(campo)) != valor_comparable(campo, valor)
            }
            usuario = usuario_id_sesion()
            for campo, valor in cambios_reales.items():

                if campo == "Fecha_evento" and isinstance(valor, str):
                    valor = datetime.strptime(valor, "%Y-%m-%dT%H:%M")

                modelo_operaciones.actualizar_campo_del_caso(cursor, id, campo, valor)
                modelo_auditoria.registrar_correccion(
                    cursor, id, modelo_operaciones.TABLA_CASO,
                    modelo_operaciones.CAMPOS_EDITABLES_DEL_CASO[campo], str(actual.get(campo) or ""),
                    str(valor or ""), usuario, datetime.now(), motivo)

            guardar_archivos(cursor, id, UPLOAD_FOLDERS["Operaciones"],
                             rutas_guardadas)
            rutas_eliminar = eliminar_en_transaccion(
                cursor, id, imagenes_eliminar, usuario, motivo, UPLOAD_FOLDERS["Operaciones"])
            conn.commit()
        except Exception:
            conn.rollback()
            borrar_archivos(rutas_guardadas)
            logger.exception("error_actualizar_evento")
            return jsonify({"status": "error", "message": "No fue posible actualizar el evento."}), 500

    borrar_archivos(rutas_eliminar)
    return jsonify({"status": "success", "message": "Información del evento actualizada.",
                    "cambios": len(cambios_reales), "archivos_eliminados": len(imagenes_eliminar)})


@fachada.Modulo_unificado.route("/Operaciones/operador/<codigo>")
@login_required
def consultar_operador(codigo):
    verificar_acceso_modulo("Operaciones")

    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        conductor = modelo_operaciones.buscar_nombre_del_operador(cursor, codigo.strip())
        return jsonify({"existe": bool(conductor), "nombre": conductor[0] if conductor else ""})


@fachada.Modulo_unificado.route("/Operaciones/eliminar_evento/<int:id>", methods=["POST"])
@login_required
@requiere_permiso("Eliminar_evento")
def eliminar_evento(id):
    verificar_acceso_modulo("Operaciones")
    datos = request.get_json(silent=True) or {}
    motivo = (datos.get("motivo_modificacion") or "").strip()
    if not motivo:
        return jsonify({"status": "error", "message": "El motivo del cambio es obligatorio."}), 400

    # closing() cierra cursor y conexión siempre; el rollback ocurre antes, en el except.
    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        try:
            evento = modelo_operaciones.buscar_estado_para_eliminar(cursor, id)
            if not evento:
                return jsonify({"status": "error", "message": "No se encontró el evento."}), 404
            if not usuario_puede_acceder_uf(evento[1]):
                return jsonify({"status": "error", "message": "No tiene acceso a este caso."}), 403
            if evento[0]:
                return jsonify({"status": "error", "message": "El evento ya se encuentra eliminado."}), 409
            if evento[2]:
                return jsonify({"status": "error", "message": "El caso está cerrado. Debe reabrirse antes de eliminarlo."}), 409

            usuario = usuario_id_sesion()
            modelo_operaciones.registrar_eliminacion(cursor, id, usuario, datetime.now(), motivo)
            if modelo_operaciones.marcar_caso_eliminado(cursor, id) != 1:
                conn.rollback()
                return jsonify({"status": "error", "message": "El evento ya se encuentra eliminado."}), 409

            conn.commit()
            return jsonify({"status": "success", "message": "Caso eliminado correctamente."})
        except Exception:
            conn.rollback()
            logger.exception("error_eliminar_evento")
            return jsonify({"status": "error", "message": "No fue posible eliminar el evento."}), 500
