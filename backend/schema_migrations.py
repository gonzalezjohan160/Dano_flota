"""Migraciones explícitas de SQL Server y validación del esquema requerido."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from pathlib import Path
from typing import Callable


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
HISTORY_TABLE = "dbo.SchemaMigrations"


class MigrationError(RuntimeError):
    """Error de migración claro y accionable, sin detalles del controlador."""


class SchemaValidationError(RuntimeError):
    """Falta una tabla o columna requerida, o su definición es incompatible."""


@dataclass(frozen=True)
class Migration:
    version: int
    filename: str
    sql: str
    checksum: str


@dataclass(frozen=True)
class RequiredColumn:
    table: str
    column: str
    sql_type: str
    max_length: int | None
    nullable: bool | None
    default: str | None


REQUIRED_COLUMNS = (
    # El inicio de sesión y protect_rutas leen este indicador; interpretan NULL como 0.
    RequiredColumn("Table_usuarios", "Cambio_password_obligatorio", "bit", 1, None, "0"),
    # El listado común y la ruta de borrado lógico usan ISNULL(..., 0).
    RequiredColumn("table_damage_to_fleet", "eliminado", "bit", 1, None, "0"),
    # Operaciones guarda SI/NO/NO APLICA o NULL; no se debe asignar valor predeterminado.
    RequiredColumn("table_info_oper", "responsabilidad_operador", "varchar", 20, True, None),
    # Operaciones guarda SI/NO o NULL; no se debe asignar valor predeterminado.
    RequiredColumn("table_info_oper", "conciliacion", "varchar", 10, True, None),
    # Tutoriales lista y guarda el título de cada video (NVARCHAR(200) = 400 bytes).
    RequiredColumn("table_tutoriales", "Titulo", "nvarchar", 400, True, None),
)


def load_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Lee las migraciones ordenadas; cada archivo es un único bloque T-SQL, sin GO."""
    migrations = []
    seen_versions: set[int] = set()
    pattern = re.compile(r"^(\d{3,})_[a-z0-9][a-z0-9_-]*\.sql$")

    for path in sorted(directory.glob("*.sql")):
        match = pattern.fullmatch(path.name)
        if not match:
            raise MigrationError(f"Nombre de migración no válido: {path.name}.")
        version = int(match.group(1))
        if version in seen_versions:
            raise MigrationError(f"Hay más de una migración para la versión {version}.")
        seen_versions.add(version)
        try:
            sql = path.read_text(encoding="utf-8-sig")
        except OSError:
            raise MigrationError(f"No se pudo leer la migración {path.name}.") from None
        if not sql.strip():
            raise MigrationError(f"La migración {path.name} está vacía.")
        if re.search(r"(?im)^\s*GO\s*(?:--.*)?$", sql):
            raise MigrationError(
                f"La migración {path.name} contiene GO; cada archivo debe ser un único batch T-SQL."
            )
        migrations.append(Migration(
            version=version,
            filename=path.name,
            sql=sql,
            checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        ))

    if not migrations:
        raise MigrationError(f"No hay migraciones SQL en {directory}.")
    ordered = sorted(migrations, key=lambda migration: migration.version)
    expected_versions = list(range(1, ordered[-1].version + 1))
    actual_versions = [migration.version for migration in ordered]
    if actual_versions != expected_versions:
        raise MigrationError("La secuencia de migraciones debe iniciar en 001 y no tener versiones faltantes.")
    return ordered


def _normalized_default(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"[()\s+]", "", value).lower()


def validate_required_schema(conn) -> None:
    """Valida las columnas que usan login, borrado lógico, Operaciones y Tutoriales."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.name, c.name, TYPE_NAME(c.user_type_id), c.max_length,
               c.is_nullable, dc.definition
        FROM sys.tables AS t
        INNER JOIN sys.schemas AS s ON s.schema_id = t.schema_id
        INNER JOIN sys.columns AS c ON c.object_id = t.object_id
        INNER JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
        LEFT JOIN sys.default_constraints AS dc
            ON dc.parent_object_id = c.object_id
           AND dc.parent_column_id = c.column_id
        WHERE s.name = N'dbo'
          AND ((t.name = N'Table_usuarios' AND c.name = N'Cambio_password_obligatorio')
            OR (t.name = N'table_damage_to_fleet' AND c.name = N'eliminado')
            OR (t.name = N'table_info_oper' AND c.name IN (N'responsabilidad_operador', N'conciliacion'))
            OR (t.name = N'table_tutoriales' AND c.name = N'Titulo'))
    """)
    found = {(row[0].lower(), row[1].lower()): row for row in cursor.fetchall()}
    problems = []

    for expected in REQUIRED_COLUMNS:
        row = found.get((expected.table.lower(), expected.column.lower()))
        label = f"dbo.{expected.table}.{expected.column}"
        if row is None:
            problems.append(f"falta {label}")
            continue
        _, _, actual_type, actual_length, actual_nullable, actual_default = row
        if str(actual_type).lower() != expected.sql_type:
            problems.append(f"{label} debe ser {expected.sql_type}")
            continue
        if expected.max_length is not None and actual_length != expected.max_length:
            problems.append(f"{label} debe tener longitud {expected.max_length}")
        # Se admiten indicadores BIT que acepten nulos porque la aplicación los lee con ISNULL(..., 0).
        if expected.nullable is not None and bool(actual_nullable) != expected.nullable:
            problems.append(f"{label} tiene nulabilidad incompatible")
        normalized = _normalized_default(actual_default)
        if expected.default is not None and normalized != expected.default:
            problems.append(f"{label} debe tener valor predeterminado ({expected.default})")
        if expected.default is None and actual_default is not None:
            problems.append(f"{label} no debe tener un valor predeterminado")

    if problems:
        raise SchemaValidationError(
            "Esquema SQL Server incompatible: " + "; ".join(problems)
            + ". Aplique las migraciones pendientes con `python manage_db.py migrate` y vuelva a validar."
        )


def _acquire_lock(cursor) -> None:
    cursor.execute("""
        DECLARE @result int;
        EXEC @result = sys.sp_getapplock
            @Resource = N'dano_flota_schema_migrations',
            @LockMode = N'Exclusive',
            @LockOwner = N'Session',
            @LockTimeout = 60000,
            @DbPrincipal = N'public';
        SELECT @result;
    """)
    row = cursor.fetchone()
    if not row or row[0] < 0:
        raise MigrationError("No se pudo obtener el bloqueo de migraciones de SQL Server.")


def _release_lock(cursor) -> None:
    cursor.execute("""
        DECLARE @result int;
        EXEC @result = sys.sp_releaseapplock
            @Resource = N'dano_flota_schema_migrations',
            @LockOwner = N'Session',
            @DbPrincipal = N'public';
        SELECT @result;
    """)
    cursor.fetchone()


def _ensure_history_table(cursor) -> None:
    cursor.execute("""
        IF OBJECT_ID(N'dbo.SchemaMigrations', N'U') IS NULL
        BEGIN
            CREATE TABLE dbo.SchemaMigrations (
                Version int NOT NULL CONSTRAINT PK_SchemaMigrations PRIMARY KEY,
                FileName nvarchar(255) NOT NULL,
                ContentHash char(64) NOT NULL,
                AppliedAt datetime2(0) NOT NULL
                    CONSTRAINT DF_SchemaMigrations_AppliedAt DEFAULT (SYSUTCDATETIME())
            );
        END;
    """)


def _check_prerequisite_tables(cursor) -> None:
    cursor.execute("""
        SELECT name
        FROM sys.tables
        WHERE schema_id = SCHEMA_ID(N'dbo')
          AND name IN (N'Table_usuarios', N'table_damage_to_fleet', N'table_info_oper')
    """)
    found = {str(row[0]).lower() for row in cursor.fetchall()}
    required = {"table_usuarios", "table_damage_to_fleet", "table_info_oper"}
    missing = sorted(required - found)
    if missing:
        names = ", ".join(f"dbo.{name}" for name in missing)
        raise MigrationError(
            f"Faltan tablas requeridas ({names}). Ejecute primero el script de esquema base en una base vacía."
        )


def _read_history(cursor) -> dict[int, tuple[str, str]]:
    cursor.execute("SELECT Version, FileName, ContentHash FROM dbo.SchemaMigrations ORDER BY Version")
    history = {}
    for version, filename, checksum in cursor.fetchall():
        version = int(version)
        if version in history:
            raise MigrationError(f"El historial contiene la versión duplicada {version}.")
        history[version] = (str(filename), str(checksum).strip())
    return history


def apply_migrations(conn, directory: Path = MIGRATIONS_DIR) -> tuple[list[str], list[str]]:
    """Aplica cada migración pendiente en una transacción junto con su registro en el historial."""
    migrations = load_migrations(directory)
    cursor = conn.cursor()
    lock_acquired = False
    applied: list[str] = []
    already_applied: list[str] = []

    try:
        _acquire_lock(cursor)
        lock_acquired = True
        _check_prerequisite_tables(cursor)
        _ensure_history_table(cursor)
        conn.commit()
        history = _read_history(cursor)
        by_version = {migration.version: migration for migration in migrations}

        for version, (filename, checksum) in history.items():
            migration = by_version.get(version)
            if migration is None:
                raise MigrationError(f"La versión {version} está en el historial, pero no existe su archivo.")
            if filename != migration.filename:
                raise MigrationError(
                    f"La versión {version} está registrada como {filename}, pero el archivo disponible es {migration.filename}."
                )
            if checksum != migration.checksum:
                raise MigrationError(f"El contenido de la migración aplicada {filename} fue modificado.")
            already_applied.append(filename)

        applied_versions = set(history)
        for migration in migrations:
            if migration.version in applied_versions:
                continue
            if any(version > migration.version for version in applied_versions):
                raise MigrationError(
                    f"No se puede aplicar {migration.filename}: hay versiones posteriores registradas con un hueco anterior."
                )
            try:
                cursor.execute(migration.sql)
                cursor.execute("""
                    INSERT INTO dbo.SchemaMigrations (Version, FileName, ContentHash)
                    VALUES (?, ?, ?)
                """, migration.version, migration.filename, migration.checksum)
                conn.commit()
            except Exception:
                conn.rollback()
                raise MigrationError(
                    f"Falló la migración {migration.filename}; se revirtió su transacción y no se registró como aplicada."
                ) from None
            applied.append(migration.filename)
            applied_versions.add(migration.version)

        return applied, already_applied
    except MigrationError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise MigrationError(
            "No fue posible preparar el historial o ejecutar las migraciones. Verifique la conexión y los permisos SQL Server."
        ) from None
    finally:
        if lock_acquired:
            try:
                _release_lock(cursor)
            except Exception:
                # Cerrar la conexión también libera el bloqueo de aplicación de la sesión.
                pass


def validate_connection(connect: Callable[[], object]) -> None:
    """Conecta y valida sin exponer mensajes del controlador ni datos de conexión."""
    try:
        conn = connect()
    except Exception:
        raise ConnectionError("No fue posible conectar con SQL Server.") from None
    try:
        validate_required_schema(conn)
    finally:
        conn.close()
