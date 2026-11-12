"""Módulo unificado de gestión de casos: Operaciones, Mtto, Svial y RRLL.

Este archivo es la FACHADA del módulo:
  * crea el blueprint Modulo_unificado (lo registra backend_interfaz.py);
  * conserva la conexión (connect) y la verificación de UF del caso;
  * expone los nombres que usan autorizacion.py, backend_interfaz.py y las pruebas.

Las rutas viven en el paquete unificado/ (un controlador por dominio) y se
registran al final de este archivo, una sola vez. Los controladores llaman a
la sesion de repositories/ y fachada.verificar_acceso_uf_caso() a través de este módulo,
así que sustituirlos aquí (pruebas) los afecta a todos.
"""
from repositories.sesiones import sesion_bd
from contextlib import closing

from flask import Blueprint, abort, jsonify, make_response

from backend_security import usuario_puede_acceder_uf
from config import BASE_DIR, UPLOAD_FOLDERS, connect
from modelos import casos as modelo_casos
from servicios.flujo_caso import (
    PROCESOS_PENDIENTES_RRLL,
    cerrar_caso_automaticamente,
    evento_pendiente_para_modulo,
    normalizar_procesos_pendientes,
    requiere_relaciones_laborales,
)
from unificado.configuracion import (
    ARCHIVOS_POR_TIPO,
    CONFIG_GESTIONES,
    MODULOS,
    PERMISOS_VER_ADJUNTOS_CASO,
)
from servicios.montos import MAXIMO_MONTO_APLICACION
from unificado.comun import (
    config_publica_modulo,
    leer_valor_monetario,
    validar_adjuntos_de_solicitud,
    verificar_acceso_modulo,
)

Modulo_unificado = Blueprint(
    "Modulo_unificado",
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)


def verificar_acceso_uf_caso(id_caso, exigir_abierto=False):
    """Carga el caso por Id y valida UF y estado antes de consultarlo o gestionarlo.

    404 si no existe o fue eliminado, 403 si es de otra UF y, cuando la acción
    registra o modifica gestiones (exigir_abierto), 409 si el caso está cerrado.
    """
    id_texto = str(id_caso)
    if not id_texto.isascii() or not id_texto.isdecimal():
        abort(404)
    with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
        registro = modelo_casos.buscar_estado_del_caso(cursor, id_caso)

    if not registro:
        abort(404)
    uf, eliminado, cerrado = registro
    if not usuario_puede_acceder_uf(uf):
        abort(403)
    if eliminado:
        abort(404)
    if exigir_abierto and cerrado:
        abort(make_response(jsonify({
            "status": "error",
            "message": "El caso está cerrado. Debe reabrirse antes de registrar o modificar gestiones."
        }), 409))


# ==========================================================
# REGISTRO DE RUTAS (una sola vez, después de crear el blueprint)
# ==========================================================
from unificado.archivos import borrar_archivos, descargar_archivo, guardar_archivos  # noqa: E402
from unificado.bandeja import index, opciones_evento  # noqa: E402
from unificado.detalle import detalle  # noqa: E402
from unificado.gestiones import agregar  # noqa: E402
from unificado.laboral import agregar_relaciones_laborales  # noqa: E402
from unificado.operaciones import (  # noqa: E402
    agregar_operaciones,
    obtener_reincidencia_operador,
    verificar_reincidencia_operador,
)
from unificado.operaciones_evento import actualizar_evento, consultar_operador, eliminar_evento  # noqa: E402
from unificado.reapertura import reabrir_caso, reabrir_evento, reabrir_evento_laboral  # noqa: E402

# Nombres que otros módulos y las pruebas importan desde esta fachada.
__all__ = [
    "Modulo_unificado", "connect", "verificar_acceso_uf_caso", "UPLOAD_FOLDERS",
    "MODULOS", "CONFIG_GESTIONES", "ARCHIVOS_POR_TIPO", "PERMISOS_VER_ADJUNTOS_CASO",
    "MAXIMO_MONTO_APLICACION", "leer_valor_monetario", "config_publica_modulo",
    "validar_adjuntos_de_solicitud", "verificar_acceso_modulo",
    "PROCESOS_PENDIENTES_RRLL", "normalizar_procesos_pendientes", "evento_pendiente_para_modulo",
    "requiere_relaciones_laborales", "cerrar_caso_automaticamente",
    "index", "opciones_evento", "detalle", "descargar_archivo", "guardar_archivos", "borrar_archivos",
    "actualizar_evento", "consultar_operador", "eliminar_evento",
    "obtener_reincidencia_operador", "verificar_reincidencia_operador", "agregar_operaciones",
    "reabrir_caso", "reabrir_evento", "reabrir_evento_laboral",
    "agregar", "agregar_relaciones_laborales",
]
