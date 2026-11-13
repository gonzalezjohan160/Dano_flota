"""Carga transaccional y evidencias sintéticas del starter."""

import struct
import zlib
from itertools import batched
from pathlib import Path
from tempfile import TemporaryDirectory

from . import paquete, sql
from .archivos import publicar
from .politica import CARPETAS, USUARIOS, regla


def imagen_qa():
    """PNG RGB de 64×64 píxeles para probar galerías y descargas."""
    def bloque(tipo, datos):
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))

    cabecera = struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0)
    filas = (b"\x00" + b"\x24\x71\xa3" * 64) * 64
    return b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", cabecera) + bloque(
        b"IDAT", zlib.compress(filas)
    ) + bloque(b"IEND", b"")


def evidencia(raiz, carpeta, corte, tabla, archivo_id):
    if carpeta not in {*CARPETAS.values(), "Sin_clasificar"} or type(archivo_id) is not int:
        raise ValueError("La referencia de un adjunto sintético no es válida.")
    nombre = f"starter_{corte}_{archivo_id}.png"
    ruta = (raiz / "Files" / carpeta / nombre).resolve()
    if not ruta.is_relative_to(raiz) or ruta.parent != raiz / "Files" / carpeta:
        raise ValueError("La carpeta de evidencias debe estar dentro del directorio de QA.")
    contenido = imagen_qa()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not ruta.exists():
        with TemporaryDirectory(dir=ruta.parent) as temporal:
            provisional = Path(temporal) / nombre
            provisional.write_bytes(contenido)
            try:
                publicar(provisional, ruta)
            except FileExistsError:
                pass
    if ruta.read_bytes() != contenido:
        raise ValueError(f"Ya existe contenido diferente para el adjunto de {tabla}.")
    return ruta


def materializar(archivo, manifiesto, tabla, raiz, credenciales, encontrados):
    columnas = manifiesto["esquema"][tabla]
    posiciones = {col[0]: i for i, col in enumerate(columnas)}
    for fila in paquete.filas(archivo, manifiesto, tabla):
        if tabla == USUARIOS:
            usuario = paquete.alias(fila[posiciones["consid"]])
            if fila[posiciones["username"]] != usuario:
                raise ValueError("Alias inesperado en el paquete.")
            activa = usuario in credenciales
            fila[posiciones["passwordhash"]] = credenciales.get(usuario, "!")
            fila[posiciones["activo"]] = activa
            fila[posiciones["cambio_password_obligatorio"]] = True
            if activa:
                encontrados.add(usuario)
        if "filepath" in posiciones and regla(tabla, columnas[posiciones["filepath"]]) == "adjunto":
            indice = posiciones["filepath"]
            ruta = evidencia(raiz, fila[indice], manifiesto["id"], tabla, fila[posiciones["id"]])
            longitud = columnas[indice][2]
            caracteres = longitud // 2 if columnas[indice][1] == "nvarchar" else longitud
            if caracteres > 0 and len(str(ruta)) > caracteres:
                raise ValueError("La ruta de evidencias supera la longitud admitida por SQL Server.")
            fila[indice] = str(ruta)
            fila[posiciones["filename"]] = ruta.name
        yield fila


def cargar(conexion, cursor, archivo, manifiesto, esquema, raiz, credenciales):
    if manifiesto["esquema"] != esquema:
        raise ValueError("Las columnas y tipos del paquete y del destino deben coincidir.")
    paquete.comprobar(archivo, manifiesto)
    orden = sql.orden_de_carga(cursor, esquema)
    encontrados = set()
    try:
        sql.bloquear_carga(cursor, orden)
        for tabla in orden:
            filas = materializar(archivo, manifiesto, tabla, raiz, credenciales, encontrados)
            sql.insertar(cursor, tabla, esquema[tabla], batched(filas, paquete.LOTE))
        if encontrados != credenciales.keys():
            raise ValueError("Alguna cuenta seleccionada no existe en el paquete.")
        for tabla in orden:
            sql.verificar_conteo(cursor, tabla, manifiesto["tablas"][tabla]["filas"])
        conexion.commit()
    except BaseException:
        conexion.rollback()
        raise
