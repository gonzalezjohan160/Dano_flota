"""Comandos explícitos de mantenimiento; importar este módulo no ejecuta migraciones."""

import argparse
import sys

from config import connect
from schema_migrations import (
    HISTORY_TABLE,
    MigrationError,
    SchemaValidationError,
    apply_migrations,
    validate_required_schema,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Validación y migraciones explícitas de SQL Server.")
    parser.add_argument("command", choices=("migrate", "validate", "status"))
    args = parser.parse_args(argv)

    try:
        conn = connect()
    except Exception:
        print("ERROR: no fue posible conectar con SQL Server. Revise la configuración y disponibilidad.", file=sys.stderr)
        return 2

    try:
        if args.command == "migrate":
            applied, already = apply_migrations(conn)
            validate_required_schema(conn)
            for filename in applied:
                print(f"Aplicada: {filename}")
            for filename in already:
                print(f"Ya aplicada: {filename}")
            if not applied:
                print("No hay migraciones pendientes.")
            return 0

        if args.command == "validate":
            validate_required_schema(conn)
            print("Esquema requerido validado correctamente.")
            return 0

        cursor = conn.cursor()
        cursor.execute(f"SELECT Version, FileName, AppliedAt FROM {HISTORY_TABLE} ORDER BY Version")
        rows = cursor.fetchall()
        for version, filename, applied_at in rows:
            print(f"{version}: {filename} ({applied_at})")
        if not rows:
            print("El historial existe y aún no registra migraciones.")
        return 0
    except (MigrationError, SchemaValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("ERROR: no fue posible completar la operación de esquema. Revise el log del servidor SQL.", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
