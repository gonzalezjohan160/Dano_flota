"""Acceso a SQL Server para la herramienta de entrega de QA."""

from graphlib import TopologicalSorter

from .politica import (
    ARCHIVOS, EXCLUIDAS, OPCIONALES, REPARACIONES_ARCHIVOS, REQUERIDAS, USUARIOS,
    regla, valor_proyectado,
)


def identificador(nombre):
    return "[" + nombre.replace("]", "]]") + "]"


def objeto(tabla):
    return ".".join(map(identificador, tabla.split(".")))


def identidad(cursor, servidor, base, destino):
    cursor.execute("""
        SELECT CONVERT(nvarchar(128), SERVERPROPERTY('ServerName')), DB_NAME(),
               CONVERT(nvarchar(20), DATABASEPROPERTYEX(DB_NAME(), 'Updateability')),
               (SELECT CONVERT(nvarchar(30), value) FROM sys.extended_properties
                WHERE class = 0 AND name = N'DanoFlotaStarterDestino')
    """)
    real_servidor, real_base, modo, marca = cursor.fetchone()
    if not real_servidor or (real_servidor.casefold(), real_base.casefold()) != (
        servidor.casefold(), base.casefold()
    ):
        raise ValueError("La identidad de SQL Server no coincide con el servidor y base indicados.")
    if destino:
        if not real_base.lower().endswith("_qa") or marca != "qa" or modo != "READ_WRITE":
            raise ValueError("El destino requiere una base *_qa de escritura marcada para el starter.")
    elif modo != "READ_ONLY":
        raise ValueError("La exportación requiere una copia aislada de solo lectura.")


def esquema(cursor):
    cursor.execute("""
        SELECT LOWER(s.name + '.' + t.name), LOWER(c.name), LOWER(ty.name),
               c.max_length, c.precision, c.scale, c.is_nullable, c.is_identity
        FROM sys.tables AS t
        JOIN sys.schemas AS s ON t.schema_id = s.schema_id
        JOIN sys.columns AS c ON c.object_id = t.object_id
        JOIN sys.types AS ty ON c.user_type_id = ty.user_type_id
        WHERE c.is_computed = 0 AND c.generated_always_type = 0 AND ty.name <> N'timestamp'
        ORDER BY LOWER(s.name + '.' + t.name), LOWER(c.name)
    """)
    tablas = {}
    for tabla, *columna in cursor:
        if tabla in REQUERIDAS or tabla in OPCIONALES:
            regla(tabla, columna)
            tablas.setdefault(tabla, []).append(columna)
    faltan = set(REQUERIDAS) - tablas.keys()
    if faltan:
        raise ValueError("Faltan tablas del esquema físico: " + ", ".join(sorted(faltan)))
    indispensables = {
        USUARIOS: {"consid", "username", "passwordhash", "activo", "cambio_password_obligatorio", "alcance_uf"},
        ARCHIVOS: {"id", "filename", "filepath"},
        REPARACIONES_ARCHIVOS: {"id", "filename", "filepath"},
    }
    for tabla, requeridas in indispensables.items():
        faltan = requeridas - {col[0] for col in tablas[tabla]}
        if faltan:
            raise ValueError(f"Faltan columnas en {tabla}: {', '.join(sorted(faltan))}.")
    cursor.execute("SELECT COL_LENGTH(N'flota.table_damage_files', N'Modulo')")
    if cursor.fetchone()[0] is None:
        raise ValueError("Falta flota.table_damage_files.Modulo.")
    return tablas


def orden_de_carga(cursor, tablas):
    cursor.execute("""
        SELECT LOWER(SCHEMA_NAME(t.schema_id) + '.' + t.name),
               LOWER(SCHEMA_NAME(p.schema_id) + '.' + p.name), f.is_disabled
        FROM sys.foreign_keys AS f
        JOIN sys.tables AS t ON t.object_id = f.parent_object_id
        JOIN sys.tables AS p ON p.object_id = f.referenced_object_id
    """)
    grafo = TopologicalSorter()
    for tabla in tablas:
        grafo.add(tabla)
    for hija, padre, desactivada in cursor:
        if hija not in tablas:
            continue
        if desactivada or padre == hija or padre not in tablas:
            raise ValueError(f"Dependencia incompatible con el starter: {hija} → {padre}.")
        grafo.add(hija, padre)
    return tuple(grafo.static_order())


def leer_filas(cursor, tabla, columnas):
    campos = [valor_proyectado(col, regla(tabla, col)) for col in columnas]
    if tabla == ARCHIVOS:
        campos.append("[Modulo]")
    cursor.execute(f"SELECT {', '.join(campos)} FROM {objeto(tabla)}")
    yield from cursor


def bloquear_carga(cursor, tablas):
    cursor.execute("""
        SET NOCOUNT ON;
        SET XACT_ABORT ON;
        DECLARE @resultado int;
        EXEC @resultado = sys.sp_getapplock @Resource = N'dano_flota_qa_starter',
            @LockMode = 'Exclusive', @LockOwner = 'Session', @LockTimeout = 0;
        SELECT @resultado;
    """)
    if cursor.fetchone()[0] < 0:
        raise ValueError("Ya existe otra carga del starter en el destino.")
    for tabla in (*tablas, *EXCLUIDAS):
        if tabla in EXCLUIDAS:
            cursor.execute("SELECT OBJECT_ID(?, 'U')", tabla)
            if cursor.fetchone()[0] is None:
                continue
        cursor.execute(f"SELECT TOP (1) 1 FROM {objeto(tabla)} WITH (TABLOCKX, HOLDLOCK)")
        if cursor.fetchone() is not None:
            raise ValueError(f"El destino debe estar vacío: {tabla} contiene filas.")


def insertar(cursor, tabla, columnas, lotes):
    destino = objeto(tabla)
    nombres = ", ".join(identificador(col[0]) for col in columnas)
    parametros = ", ".join("?" for _ in columnas)
    comando = f"INSERT INTO {destino} ({nombres}) VALUES ({parametros})"
    identidad_activa = any(col[-1] for col in columnas)
    if identidad_activa:
        cursor.execute(f"SET IDENTITY_INSERT {destino} ON")
    for lote in lotes:
        cursor.executemany(comando, lote)
    if identidad_activa:
        cursor.execute(f"SET IDENTITY_INSERT {destino} OFF")


def verificar_conteo(cursor, tabla, esperado):
    cursor.execute(f"SELECT COUNT_BIG(*) FROM {objeto(tabla)}")
    if cursor.fetchone()[0] != esperado:
        raise ValueError(f"El conteo cargado no coincide para {tabla}.")
