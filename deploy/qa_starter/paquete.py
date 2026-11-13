"""Generación y lectura del paquete de datos enmascarados."""

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from .archivos import publicar
from .politica import ARCHIVOS, CARPETAS, USUARIOS, regla
from .sql import leer_filas

VERSION = 1
LOTE = 500


def codificar(valor):
    if isinstance(valor, Decimal):
        return str(valor)
    raise TypeError("Tipo de dato no serializable en el starter.")


def alias(consid):
    return f"qa_{consid}"


def enmascarar(tabla, columnas, fila, codigos):
    valores = dict(zip((col[0] for col in columnas), fila))
    usuario = alias(valores["consid"]) if tabla == USUARIOS else None
    resultado = []
    for col, valor in zip(columnas, fila):
        accion = regla(tabla, col)
        if accion == "usuario":
            valor = usuario
        elif accion == "correo":
            valor = f"{usuario}@example.invalid"
        elif accion == "identificacion":
            valor = valores["consid"]
        elif accion == "inactivo":
            valor = False
        elif accion == "cambio":
            valor = True
        elif accion == "ocultar" and valor is not None:
            limite = col[2] // (2 if col[1] in {"nchar", "nvarchar"} else 1)
            valor = "Dato de QA"[:limite] if limite > 0 else "Dato de QA"
        elif accion == "codigo" and valor is not None:
            original = valor.strip().casefold()
            if original:
                prefijo = original[0] if original[0] in "1234567" else "9"
                valor = codigos.setdefault(original, f"{prefijo}{len(codigos) + 1:09d}")
            else:
                valor = ""
        elif accion == "adjunto":
            modulo = str(fila[-1]).strip() if tabla == ARCHIVOS else "Reparaciones"
            carpeta = CARPETAS.get(modulo)
            if carpeta is None:
                # Conservar la clasificación original sin conservar la ruta.
                carpeta = "Sin_clasificar"
            valor = carpeta if col[0] == "filepath" else None
        resultado.append(valor)
    return resultado


def escribir_tabla(archivo, cursor, tabla, columnas, codigos):
    huella = hashlib.sha256()
    cantidad = 0
    with archivo.open(f"{tabla}.jsonl", "w", force_zip64=True) as salida:
        for fila in leer_filas(cursor, tabla, columnas):
            valores = enmascarar(tabla, columnas, fila, codigos)
            linea = (json.dumps(valores, default=codificar, allow_nan=False) + "\n").encode()
            salida.write(linea)
            huella.update(linea)
            cantidad += 1
    return {"filas": cantidad, "sha256": huella.hexdigest()}


def crear(cursor, esquema, destino):
    destino = Path(destino)
    manifiesto = {
        "version": VERSION, "id": uuid4().hex,
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "esquema": esquema, "tablas": {},
    }
    codigos = {}
    with TemporaryDirectory(dir=destino.parent) as temporal:
        ruta = Path(temporal) / "starter.zip"
        with ZipFile(ruta, "w", compression=ZIP_DEFLATED) as archivo:
            for tabla, columnas in esquema.items():
                manifiesto["tablas"][tabla] = escribir_tabla(archivo, cursor, tabla, columnas, codigos)
            archivo.writestr("manifiesto.json", json.dumps(manifiesto, indent=2))
        # Publicación atómica y sin sobrescribir un corte anterior.
        publicar(ruta, destino)
    return manifiesto


def leer_manifiesto(archivo):
    datos = json.loads(archivo.read("manifiesto.json"))
    if datos["version"] != VERSION or UUID(hex=datos["id"]).hex != datos["id"]:
        raise ValueError("Versión o identificador de paquete inválido.")
    tablas = set(datos["esquema"])
    esperados = {"manifiesto.json", *(f"{tabla}.jsonl" for tabla in tablas)}
    if tablas != set(datos["tablas"]) or sorted(archivo.namelist()) != sorted(esperados):
        raise ValueError("Las entradas del paquete no coinciden con el manifiesto.")
    return datos


def filas(archivo, manifiesto, tabla):
    huella = hashlib.sha256()
    cantidad = 0
    columnas = manifiesto["esquema"][tabla]
    with archivo.open(f"{tabla}.jsonl") as entrada:
        for linea in entrada:
            huella.update(linea)
            fila = json.loads(linea)
            if not isinstance(fila, list) or len(fila) != len(columnas):
                raise ValueError(f"Fila incompatible con el esquema de {tabla}.")
            cantidad += 1
            yield fila
    esperado = manifiesto["tablas"][tabla]
    if cantidad != esperado["filas"] or huella.hexdigest() != esperado["sha256"]:
        raise ValueError(f"Conteo o huella inválida en {tabla}.")


def comprobar(archivo, manifiesto):
    for tabla in manifiesto["esquema"]:
        for _ in filas(archivo, manifiesto, tabla):
            pass
