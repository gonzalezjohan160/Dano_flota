"""Punto de entrada: python -m deploy.qa_starter."""

import argparse
import getpass
import json
import os
import re
import sys
from contextlib import closing
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from . import carga, media, paquete, sql
from .politica import USUARIOS, regla


def argumentos(argv):
    parser = argparse.ArgumentParser(description="Respaldo de adjuntos y starter de Dano_flota para QA.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    for nombre in ("plan", "exportar", "cargar"):
        comando = comandos.add_parser(nombre)
        comando.add_argument("--servidor", required=True, help="Valor de SERVERPROPERTY('ServerName').")
        comando.add_argument("--base", required=True, help="Nombre exacto de la base conectada.")
        if nombre != "plan":
            comando.add_argument("paquete", type=Path)
        else:
            comando.add_argument("--destino", action="store_true", help="Comprueba el destino QA.")
        if nombre == "cargar":
            comando.add_argument("--media", required=True, type=Path, help="MEDIA_DIR de la app QA.")
            comando.add_argument("--activar", action="append", default=[], metavar="QA_ID")
    for nombre in ("verificar", "cuentas"):
        comandos.add_parser(nombre).add_argument("paquete", type=Path)
    for nombre in ("respaldar-adjuntos", "restaurar-adjuntos"):
        comando = comandos.add_parser(nombre)
        comando.add_argument("origen", type=Path)
        comando.add_argument("destino", type=Path)
    return parser.parse_args(argv)


def credenciales_de_qa(aliases):
    from werkzeug.security import generate_password_hash

    resultado = {}
    for alias in aliases:
        if re.fullmatch(r"qa_-?\d+", alias) is None or alias in resultado:
            raise ValueError("Use aliases distintos del inventario de cuentas.")
        if not sys.stdin.isatty():
            raise ValueError("La activación de cuentas requiere una terminal interactiva.")
        clave = getpass.getpass(f"Contraseña temporal de {alias}: ")
        if (len(clave) < 10 or not any(c.islower() for c in clave) or
                not any(c.isupper() for c in clave) or not any(c.isdigit() for c in clave) or
                alias.casefold() in clave.casefold()):
            raise ValueError("La contraseña debe tener 10 caracteres, mayúscula, minúscula y número.")
        if clave != getpass.getpass("Repita la contraseña temporal: "):
            raise ValueError("Las contraseñas ingresadas no coinciden.")
        resultado[alias] = generate_password_hash(clave)
    return resultado


def imprimir_conteos(manifiesto):
    print(f"Paquete {manifiesto['id']}")
    for tabla, datos in manifiesto["tablas"].items():
        print(f"{tabla}: {datos['filas']}")


def imprimir_cuentas(archivo, manifiesto):
    def registros(tabla):
        columnas = [col[0] for col in manifiesto["esquema"][tabla]]
        for fila in paquete.filas(archivo, manifiesto, tabla):
            yield dict(zip(columnas, fila, strict=True))

    permisos = {r["permisoid"]: r["nombre"] for r in registros("usuario.table_permisos")}
    por_usuario = {}
    for fila in registros("usuario.table_usuarios_permisos"):
        por_usuario.setdefault(fila["userid"], []).append(permisos[fila["permisoid"]])
    print("Alias\tAlcance UF\tPermisos")
    for fila in registros(USUARIOS):
        nombres = ", ".join(sorted(por_usuario.get(fila["consid"], [])))
        print(f"{fila['username']}\t{fila['alcance_uf'] or ''}\t{nombres}")


def operar_bd(args):
    import pyodbc

    destino = args.comando == "cargar" or getattr(args, "destino", False)
    variable = "DANO_STARTER_QA_ODBC" if destino else "DANO_STARTER_ORIGEN_ODBC"
    cadena = os.getenv(variable)
    if not cadena:
        raise ValueError(f"Falta configurar {variable}.")
    pyodbc.pooling = False
    with closing(pyodbc.connect(cadena, timeout=10)) as conexion, closing(conexion.cursor()) as cursor:
        sql.identidad(cursor, args.servidor, args.base, destino)
        esquema = sql.esquema(cursor)
        if args.comando == "plan":
            sql.orden_de_carga(cursor, esquema)
            print(json.dumps({tabla: {col[0]: regla(tabla, col) for col in columnas}
                              for tabla, columnas in esquema.items()}, indent=2))
        elif args.comando == "exportar":
            imprimir_conteos(paquete.crear(cursor, esquema, args.paquete))
        else:
            if not args.media.is_absolute():
                raise ValueError("--media debe ser la ruta absoluta de los adjuntos de QA.")
            with ZipFile(args.paquete) as archivo:
                manifiesto = paquete.leer_manifiesto(archivo)
                carga.cargar(conexion, cursor, archivo, manifiesto, esquema, args.media.resolve(),
                             credenciales_de_qa(args.activar))
            imprimir_conteos(manifiesto)


def main(argv=None):
    args = argumentos(argv)
    try:
        if args.comando == "respaldar-adjuntos":
            media.guardar(args.origen, args.destino)
        elif args.comando == "restaurar-adjuntos":
            media.restaurar(args.origen, args.destino)
        elif args.comando in {"verificar", "cuentas"}:
            with ZipFile(args.paquete) as archivo:
                manifiesto = paquete.leer_manifiesto(archivo)
                paquete.comprobar(archivo, manifiesto)
                if args.comando == "cuentas":
                    imprimir_cuentas(archivo, manifiesto)
                else:
                    imprimir_conteos(manifiesto)
        else:
            operar_bd(args)
    except (OSError, ValueError, TypeError, KeyError, BadZipFile) as error:
        print(f"Error del starter: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        # Los mensajes del controlador pueden incluir parámetros de conexión o valores SQL.
        print(f"Falló {args.comando} ({type(error).__name__}). Revise los registros de SQL Server "
              "o repita el plan con el esquema y los permisos del ambiente.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
