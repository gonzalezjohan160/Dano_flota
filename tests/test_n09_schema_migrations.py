import hashlib
from pathlib import Path
import tempfile
import unittest

from backend.schema_migrations import (
    MigrationError,
    SchemaValidationError,
    apply_migrations,
    load_migrations,
    validate_connection,
    validate_required_schema,
)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, sql, *params):
        normalized = " ".join(sql.split())
        if "sp_getapplock" in normalized or "sp_releaseapplock" in normalized:
            self.result = (0,)
        elif "sys.default_constraints AS dc" in normalized and "TYPE_NAME(c.user_type_id)" in normalized:
            self.result = list(self.connection.schema_rows)
        elif "FROM sys.tables" in normalized:
            # Requisito previo: cuántas de las tablas pedidas existen.
            self.result = [(sum(1 for nombre in params if nombre in self.connection.available_tables),)]
        elif "CREATE TABLE dbo.SchemaMigrations" in normalized:
            self.connection.history_exists = True
        elif normalized.startswith("SELECT Version, FileName, ContentHash"):
            self.result = [
                (version, filename, checksum)
                for version, (filename, checksum) in sorted(self.connection.history.items())
            ]
        elif normalized.startswith("INSERT INTO dbo.SchemaMigrations"):
            version, filename, checksum = params
            if version in self.connection.history:
                raise RuntimeError("duplicate")
            self.connection.history[version] = (filename, checksum)
        elif "FAIL_MIGRATION" in normalized:
            self.connection.executed.append(sql)
            raise RuntimeError("simulated SQL error")
        elif normalized.startswith("SELECT"):
            self.result = []
        else:
            self.connection.executed.append(sql)
        return self

    def fetchone(self):
        if isinstance(self.result, list):
            return self.result[0] if self.result else None
        return self.result

    def fetchall(self):
        return self.result or []

    def nextset(self):
        return False


class FakeConnection:
    def __init__(self, schema_rows=(), available_tables=("usuario.Table_usuarios",)):
        self.schema_rows = schema_rows
        self.available_tables = available_tables
        self.history = {}
        self.history_exists = False
        self.executed = []
        self._snapshot = None

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self._snapshot = (dict(self.history), self.history_exists, list(self.executed))

    def rollback(self):
        if self._snapshot is not None:
            self.history, self.history_exists, self.executed = (
                dict(self._snapshot[0]), self._snapshot[1], list(self._snapshot[2])
            )

    def close(self):
        pass


def complete_schema():
    return [
        ("usuario", "Table_usuarios", "Cambio_password_obligatorio", "bit", 1, 0, "((0))"),
        ("flota", "table_damage_to_fleet", "eliminado", "bit", 1, 0, "((0))"),
        ("usuario", "Table_usuarios", "Alcance_UF", "varchar", 20, 1, None),
        ("flota", "table_damage_to_fleet", "estado_caso", "bit", 1, 0, "((0))"),
        ("flota", "table_damage_to_fleet", "usuario_id", "int", 4, 1, None),
        ("proceso", "table_info_oper", "usuario_id", "int", 4, 0, None),
        ("proceso", "table_info_mtto", "usuario_id", "int", 4, 1, None),
        ("proceso", "table_info_svial", "usuario_id", "int", 4, 0, None),
        ("proceso", "table_info_labora", "usuario_id", "int", 4, 0, None),
        ("proceso", "table_info_laboral_mult", "usuario_id", "int", 4, 1, None),
        ("proceso", "table_auditoria_correcciones", "usuario_id", "int", 4, 1, None),
        ("proceso", "table_intervenciones", "usuario_id", "int", 4, 0, None),
        ("usuario", "table_tutoriales", "Titulo", "nvarchar", 400, 1, None),
        ("proceso", "table_info_oper", "responsabilidad_operador", "varchar", 20, 1, None),
        ("proceso", "table_info_oper", "conciliacion", "varchar", 10, 1, None),
    ]


class SchemaMigrationTests(unittest.TestCase):
    def test_migration_files_are_ordered_safe_single_batches(self):
        migrations = load_migrations()
        self.assertEqual(list(range(1, 13)), [m.version for m in migrations])
        for migration in migrations:
            self.assertNotRegex(migration.sql, r"(?im)^\s*GO\s*$")
            # Cada una revisa primero el estado de la base (no corre a ciegas).
            self.assertRegex(migration.sql, r"OBJECT_ID|SCHEMA_ID|DATABASE_PRINCIPAL_ID", migration.filename)
        self.assertIn("DF_Table_usuarios_Cambio_password_obligatorio", migrations[0].sql)
        self.assertIn("DEFAULT (0)", migrations[0].sql)
        self.assertIn("varchar(20) NULL", migrations[2].sql)
        self.assertIn("varchar(10) NULL", migrations[3].sql)
        self.assertIn("CREATE TABLE dbo.table_tutoriales", migrations[4].sql)
        self.assertIn("Titulo nvarchar(200) NULL", migrations[4].sql)

    def test_duplicate_local_versions_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (directory / "001_second.sql").write_text("SELECT 2;", encoding="utf-8")
            with self.assertRaisesRegex(MigrationError, "más de una migración"):
                load_migrations(directory)

    def test_missing_local_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            (directory / "003_third.sql").write_text("SELECT 3;", encoding="utf-8")
            with self.assertRaisesRegex(MigrationError, "versiones faltantes"):
                load_migrations(directory)

    def test_go_separator_is_rejected_in_migration_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "001_with_go.sql"
            path.write_text("SELECT 1;\nGO\nSELECT 2;", encoding="utf-8")
            with self.assertRaisesRegex(MigrationError, "contiene GO"):
                load_migrations(path.parent)

    def test_runner_creates_history_applies_in_order_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "001_first.sql").write_text("SELECT 'first';", encoding="utf-8")
            (directory / "002_second.sql").write_text("SELECT 'second';", encoding="utf-8")
            conn = FakeConnection()
            applied, existing = apply_migrations(conn, directory)
            self.assertEqual(["001_first.sql", "002_second.sql"], applied)
            self.assertEqual([], existing)
            self.assertTrue(conn.history_exists)
            self.assertEqual([1, 2], list(conn.history))
            applied_again, existing_again = apply_migrations(conn, directory)
            self.assertEqual([], applied_again)
            self.assertEqual(["001_first.sql", "002_second.sql"], existing_again)
            self.assertEqual(2, len(conn.history))

    def test_history_filename_and_checksum_mismatch_stop_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            migration_path = directory / "001_current.sql"
            migration_path.write_text("SELECT 1;", encoding="utf-8")
            conn = FakeConnection()
            conn.history[1] = ("001_old_name.sql", hashlib.sha256(b"SELECT 1;").hexdigest())
            with self.assertRaisesRegex(MigrationError, "archivo disponible"):
                apply_migrations(conn, directory)
            conn.history[1] = ("001_current.sql", "0" * 64)
            with self.assertRaisesRegex(MigrationError, "fue modificado"):
                apply_migrations(conn, directory)

    def test_failed_migration_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "001_fail.sql").write_text("FAIL_MIGRATION", encoding="utf-8")
            conn = FakeConnection()
            with self.assertRaisesRegex(MigrationError, "001_fail.sql"):
                apply_migrations(conn, directory)
            self.assertNotIn(1, conn.history)

    def test_runner_checks_required_tables_before_creating_history(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "001_first.sql").write_text("SELECT 1;", encoding="utf-8")
            conn = FakeConnection(available_tables=())
            with self.assertRaisesRegex(MigrationError, "Falta la tabla de usuarios"):
                apply_migrations(conn, directory)
            self.assertFalse(conn.history_exists)

    def test_schema_validator_accepts_complete_schema_and_reports_missing_or_wrong(self):
        conn = FakeConnection(complete_schema())
        validate_required_schema(conn)

        missing = FakeConnection(complete_schema()[:-1])
        with self.assertRaisesRegex(SchemaValidationError, "falta proceso.table_info_oper.conciliacion"):
            validate_required_schema(missing)

        wrong_type_rows = complete_schema()
        wrong_type_rows[0] = ("usuario", "Table_usuarios", "Cambio_password_obligatorio", "varchar", 1, 0, None)
        with self.assertRaisesRegex(SchemaValidationError, "debe ser bit"):
            validate_required_schema(FakeConnection(wrong_type_rows))

        wrong_default_rows = complete_schema()
        wrong_default_rows[1] = ("flota", "table_damage_to_fleet", "eliminado", "bit", 1, 0, "((1))")
        with self.assertRaisesRegex(SchemaValidationError, r"valor predeterminado \(0\)"):
            validate_required_schema(FakeConnection(wrong_default_rows))

    def test_alcance_uf_admite_nvarchar_de_20_caracteres(self):
        filas = complete_schema()
        filas[2] = ("usuario", "Table_usuarios", "Alcance_UF", "nvarchar", 40, 1, None)
        validate_required_schema(FakeConnection(filas))

    def test_connection_error_is_distinct_from_schema_incompatibility(self):
        def fail_to_connect():
            raise OSError("connection string deliberately not inspected by test")

        with self.assertRaisesRegex(ConnectionError, "No fue posible conectar"):
            validate_connection(fail_to_connect)

        with self.assertRaises(SchemaValidationError):
            validate_connection(lambda: FakeConnection())

    def test_baseline_contains_the_same_four_column_contract(self):
        script = (Path(__file__).resolve().parents[1] / "SQL damage_to_fleet" / "script.sql").read_text(encoding="utf-16")
        for column in (
            "Cambio_password_obligatorio", "eliminado",
            "responsabilidad_operador", "conciliacion",
        ):
            self.assertIn(column, script)
        self.assertIn("DF_table_damage_to_fleet_eliminado", script)
        self.assertIn("DF_Table_usuarios_Cambio_password_obligatorio", script)
        self.assertIn("[responsabilidad_operador] [varchar](20) NULL", script)
        self.assertIn("[conciliacion] [varchar](10) NULL", script)
        # Tutoriales también debe crearse desde la base del repositorio.
        self.assertIn("CREATE TABLE [dbo].[table_tutoriales]", script)
        self.assertIn("[Titulo] [nvarchar](200) NULL", script)
        # Sin rutas de archivo de una instancia concreta: debe correr en cualquier servidor.
        self.assertNotIn("FILENAME", script)

    # Solo estas migraciones pueden modificar o borrar datos o estructura, con la
    # aprobación de negocio que explica cada una en su encabezado:
    #   006: limpieza (S. Vial duplicada auditada, intervenciones de prueba, adjuntos
    #        duplicados, textos 'NULL' o vacíos, espacios sobrantes, SAN ÁNDRES y
    #        enlaces de recuperación vencidos).
    #   008: renombrado; quita UF y tipología del caso (son las del móvil) y traduce
    #        el historial de correcciones a los nombres nuevos.
    #   009: quita y recrea restricciones y columnas calculadas para cambiar tipos.
    MIGRACIONES_QUE_MODIFICAN = {
        "006_limpieza_datos_auditoria.sql",
        "008_renombrar_tablas_y_columnas.sql",
        "009_tipos_de_datos.sql",
    }

    def test_migrations_do_not_update_or_delete_historical_data(self):
        for migration in load_migrations():
            if migration.filename in self.MIGRACIONES_QUE_MODIFICAN:
                continue
            # Dar permisos a un rol (GRANT) no modifica datos, y la cascada de una clave
            # foránea solo propaga cambios futuros.
            codigo = "\n".join(l for l in migration.sql.splitlines()
                               if not l.lstrip().startswith(("--", "GRANT ")))
            codigo = codigo.replace("ON UPDATE CASCADE", "")
            self.assertNotRegex(codigo, r"(?i)\b(?:UPDATE|DELETE|DROP)\b", migration.filename)
            self.assertNotRegex(codigo, r"(?i)\bWITH\s+VALUES\b", migration.filename)

    def _sql(self, version):
        migracion = {m.version: m for m in load_migrations()}[version]
        return "\n".join(l for l in migracion.sql.splitlines() if not l.lstrip().startswith("--"))

    def test_migracion_006_audita_la_gestion_de_svial_antes_de_borrarla(self):
        sql = self._sql(6)
        # Solo S. Vial se depura (la más reciente se conserva); los demás duplicados detienen la migración.
        self.assertIn("ORDER BY s.Fecha_registro DESC, s.Id DESC", sql)
        self.assertIn("THROW 51062", sql)
        self.assertLess(sql.index("INSERT INTO proceso.table_auditoria_correcciones"), sql.index("DELETE FROM ordenadas"))
        self.assertIn("'SAN ANDRÉS'", sql)

    def test_migracion_008_verifica_uf_y_tipologia_antes_de_quitarlas(self):
        sql = self._sql(8)
        self.assertIn("THROW 51082", sql)
        self.assertLess(sql.index("THROW 51082"), sql.index("DROP COLUMN UF, Tipologia"))

    def test_migracion_009_franja_horaria_persistida(self):
        # BD-18: la fórmula debe ser determinista para admitir PERSISTED.
        sql = self._sql(9)
        self.assertIn("DATEPART(HOUR, fecha_registro)", sql)
        self.assertEqual(sql.count("PERSISTED"), 2)
        self.assertNotIn("CONVERT(TIME", sql, "la conversión desde texto no es determinista")
        self.assertIn("ALTER COLUMN fecha_registro datetime2(0) NOT NULL", sql)

    def test_migracion_010_relaciones_y_claves_foraneas(self):
        sql = self._sql(10)
        for tabla in ("gestion_operaciones", "gestion_mantenimiento", "gestion_seguridad_vial", "cierre_laboral"):
            self.assertIn(f"CONSTRAINT UQ_{tabla}_caso_id UNIQUE (caso_id)", sql)
        self.assertIn("FOREIGN KEY (movil) REFERENCES flota.movil (numero) ON UPDATE CASCADE", sql)
        self.assertIn("FOREIGN KEY (registrado_por) REFERENCES usuario.usuario (nombre_usuario) ON UPDATE CASCADE", sql)
        # El código del operador no es clave foránea: el maestro solo tiene a los activos.
        self.assertNotIn("FOREIGN KEY (codigo_operador)", sql)
        # Las correcciones de casos borrados antes del borrado lógico se conservan.
        self.assertIn("proceso.correccion WITH NOCHECK ADD", sql)
        # Decisión de negocio: no hay regla entre fecha del evento y fecha de registro.
        self.assertNotRegex(sql, r"CHECK \(fecha_evento")

    def test_ya_no_hay_migraciones_pendientes_fuera_de_la_secuencia(self):
        carpeta = Path(__file__).resolve().parents[1] / "backend" / "migrations" / "pendientes"
        self.assertFalse(carpeta.exists())

if __name__ == "__main__":
    unittest.main()
