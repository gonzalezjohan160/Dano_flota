"""Respaldo recuperable de los archivos originales del mismo corte de SQL Server."""

import shutil
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from .archivos import publicar


def guardar(raiz, destino):
    raiz = raiz.resolve(strict=True)
    destino = destino.resolve()
    if not raiz.is_dir() or destino.is_relative_to(raiz):
        raise ValueError("El respaldo debe quedar fuera de la carpeta de adjuntos.")
    with TemporaryDirectory(dir=destino.parent) as temporal:
        ruta = Path(temporal) / "adjuntos.zip"
        with ZipFile(ruta, "w", compression=ZIP_DEFLATED) as archivo:
            for entrada in sorted(raiz.rglob("*")):
                if entrada.is_symlink() or entrada.is_junction():
                    raise ValueError("El respaldo de adjuntos encontró un enlace o unión de directorio.")
                if not entrada.is_file() and not entrada.is_dir():
                    raise ValueError("El respaldo de adjuntos encontró una entrada especial.")
                archivo.write(entrada, entrada.relative_to(raiz).as_posix())
        with ZipFile(ruta) as archivo:
            if archivo.testzip() is not None:
                raise ValueError("El respaldo de adjuntos no superó la comprobación CRC.")
        publicar(ruta, destino)


def extraer(archivo, provisional):
    vistas = set()
    for entrada in archivo.infolist():
        nombre = entrada.filename.rstrip("/")
        partes = PurePosixPath(nombre).parts
        if (not partes or "/".join(partes) != nombre or
                any(parte in {".", ".."} or ":" in parte or "\\" in parte or
                    parte.endswith((".", " ")) or Path(parte).is_reserved() for parte in partes)):
            raise ValueError("El respaldo de adjuntos contiene una ruta inválida.")
        if nombre.casefold() in vistas:
            raise ValueError("El respaldo de adjuntos contiene entradas duplicadas.")
        vistas.add(nombre.casefold())
        ruta = provisional.joinpath(*partes)
        if entrada.is_dir():
            ruta.mkdir(parents=True, exist_ok=True)
        else:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            with archivo.open(entrada) as origen, ruta.open("xb") as salida:
                shutil.copyfileobj(origen, salida)


def restaurar(origen, destino):
    if destino.exists() or destino.is_symlink():
        raise FileExistsError("La carpeta de restauración debe ser nueva.")
    with TemporaryDirectory(dir=destino.parent) as temporal:
        provisional = Path(temporal) / "adjuntos"
        provisional.mkdir()
        with ZipFile(origen) as archivo:
            extraer(archivo, provisional)
        if destino.exists() or destino.is_symlink():
            raise FileExistsError("La carpeta de restauración ya existe.")
        provisional.rename(destino)
