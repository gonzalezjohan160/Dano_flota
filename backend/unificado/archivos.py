"""Adjuntos del módulo unificado: guardar, borrar y descargar por identificador.

La descarga recibe solo el Id del adjunto y su tipo; la ruta en disco sale de la
base de datos y debe quedar dentro de la carpeta de ese tipo.
"""
from repositories.sesiones import sesion_bd
import os
from contextlib import closing
from datetime import datetime
from pathlib import Path

from flask import abort, request, send_file, session
from werkzeug.utils import secure_filename

import backend_unificado as fachada
from attachment_security import (
    AttachmentValidationError,
    apply_attachment_headers,
    inline_type_for_path,
    store_upload,
    validate_uploads,
)
from backend_security import login_required, usuario_puede_acceder_uf
from config import UPLOAD_FOLDERS
from logger import logger
from modelos import archivos as modelo_archivos
from unificado.configuracion import ARCHIVOS_POR_TIPO


# ==========================================================
# VER ARCHIVO
# ==========================================================

@fachada.Modulo_unificado.route("/archivo/<int:file_id>")
@login_required
def descargar_archivo(file_id):
    tipo = request.args.get("tipo", "").lower()
    config_archivo = ARCHIVOS_POR_TIPO.get(tipo)
    if not config_archivo:
        abort(400)

    if not any(p in session.get("permisos", []) for p in config_archivo["permiso"]):
        abort(403)

    with sesion_bd(fachada.connect) as conn, closing(conn.cursor()) as cursor:
        registro = modelo_archivos.buscar_adjunto(cursor, tipo, file_id)

    if not registro or not registro[0]:
        abort(404)
    if not usuario_puede_acceder_uf(registro[2]):
        abort(403)

    # Ruta guardada en la base; debe quedar dentro de la carpeta del tipo de adjunto.
    ruta_archivo = Path(registro[0]).resolve()
    carpeta_permitida = UPLOAD_FOLDERS[config_archivo["carpeta"]].resolve()
    if carpeta_permitida not in ruta_archivo.parents:
        abort(403)
    if not ruta_archivo.is_file():
        abort(404)

    try:
        mime = inline_type_for_path(ruta_archivo)
        nombre_descarga = secure_filename(str(registro[1] or ruta_archivo.name)) or "archivo"
        respuesta = send_file(
            str(ruta_archivo),
            mimetype=mime or "application/octet-stream",
            as_attachment=mime is None,
            download_name=nombre_descarga,
        )
        return apply_attachment_headers(respuesta)
    except Exception:
        logger.exception("error_enviar_adjunto file_id=%s", file_id)
        abort(500)


# ==========================================================
# GUARDAR ARCHIVOS (usada por las gestiones)
# ==========================================================

def borrar_archivos(rutas):
    """Borra del disco los adjuntos escritos en una operación que no se confirmó."""
    for ruta in rutas:
        try:
            Path(ruta).unlink(missing_ok=True)
        except OSError:
            logger.exception("error_borrar_adjunto_huerfano")


def guardar_archivos(cursor, codigo, carpeta_base, rutas_guardadas=None):
    """Guarda los adjuntos del caso en la carpeta del módulo y los registra en
    flota.table_damage_files (la carpeta dice qué módulo los subió). Anota cada ruta en
    rutas_guardadas para que el llamador los borre si la operación falla después,
    antes del commit."""
    if rutas_guardadas is None:
        rutas_guardadas = []
    archivos = request.files.getlist("archivos")
    validate_uploads(archivos)
    codigo_seguro = str(codigo)
    if not codigo_seguro.isascii() or not codigo_seguro.isdecimal():
        raise AttachmentValidationError("El identificador del caso no es válido.")
    carpeta_base = Path(carpeta_base).resolve()
    carpeta = (carpeta_base / codigo_seguro).resolve()
    if carpeta.parent != carpeta_base:
        raise AttachmentValidationError("La ruta de almacenamiento no es válida.")
    carpeta.mkdir(parents=True, exist_ok=True)

    try:
        for archivo in archivos:
            if not archivo.filename:
                continue

            nombre_seguro = secure_filename(archivo.filename)
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            nombre = f"{os.path.splitext(nombre_seguro)[0]}_{fecha}{os.path.splitext(nombre_seguro)[1]}"
            ruta = store_upload(archivo, carpeta, nombre)
            rutas_guardadas.append(ruta)

            modelo_archivos.registrar_adjunto_del_caso(
                cursor, codigo, archivo.filename, str(ruta), datetime.now())
    except Exception:
        borrar_archivos(rutas_guardadas)
        raise
