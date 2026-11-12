"""Eliminacion auditada de imagenes existentes, dentro de la edicion del caso."""
import json
from datetime import datetime
from pathlib import Path

from modelos import archivos, auditoria

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def validar_ids_imagenes(valores):
    if not isinstance(valores, list) or len(valores) > 100:
        raise ValueError("La lista de imágenes para eliminar no es válida.")
    ids = []
    for valor in valores:
        if type(valor) is not int or not 0 < valor <= 2_147_483_647:
            raise ValueError("El identificador de la imagen no es válido.")
        if valor not in ids:
            ids.append(valor)
    return ids


def preparar_eliminacion(cursor, id_caso, ids):
    """Valida el lote completo antes de eliminar; nunca acepta rutas del cliente."""
    imagenes = []
    for identificador in ids:
        fila = archivos.buscar_imagen_de_operaciones(cursor, id_caso, identificador)
        if not fila or Path(str(fila[1] or "")).suffix.lower() not in EXTENSIONES_IMAGEN:
            raise ValueError("Solo puede eliminar imágenes de Operaciones pertenecientes a este caso.")
        imagenes.append(dict(Id=fila[0], FileName=fila[1], FilePath=fila[2]))
    return imagenes


def eliminar_en_transaccion(cursor, id_caso, imagenes, usuario_id, motivo, carpeta_permitida):
    """El llamador confirma DB; las rutas devueltas solo se borran DESPUES del commit."""
    rutas = []
    carpeta = Path(carpeta_permitida).resolve()
    for imagen in imagenes:
        archivos.eliminar_imagen_de_operaciones(cursor, id_caso, imagen["Id"])
        auditoria.registrar_correccion(
            cursor, id_caso, "flota.table_damage_files", "imagen_eliminada",
            json.dumps(imagen, ensure_ascii=False), "", usuario_id, datetime.now(), motivo)
        ruta_cruda = imagen["FilePath"]
        if ruta_cruda and not archivos.ruta_tiene_referencias(cursor, ruta_cruda):
            ruta = Path(ruta_cruda).resolve()
            # Nunca borrar fuera de la carpeta autorizada ni otra clase de archivo.
            if carpeta in ruta.parents and ruta.suffix.lower() in EXTENSIONES_IMAGEN:
                rutas.append(ruta)
    return rutas
