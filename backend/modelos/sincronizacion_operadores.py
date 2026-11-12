"""Consultas de la sincronización de operadores: flota.table_drivers contra la vista de
empleados de emoperation (em_view_employees)."""

FUENTE_SIN_CONFLICTOS = """
    SELECT code, MIN(name) AS name
    FROM [emoperation].[dbo].[em_view_employees]
    WHERE code IS NOT NULL AND name IS NOT NULL
    GROUP BY code
    HAVING COUNT(DISTINCT name) = 1
"""


def tabla_destino(cursor):
    for tabla in ("flota.table_drivers", "dbo.table_drivers"):
        cursor.execute("SELECT OBJECT_ID(?, 'U')", tabla)
        if cursor.fetchone()[0] is not None:
            return tabla
    raise RuntimeError("No se encontró table_drivers en la base de datos configurada.")


def listar_operadores_nuevos(cursor, tabla):
    """Empleados con código y nombre que aún no están en flota.table_drivers."""
    cursor.execute(f"""
            SELECT
                v.code,
                v.name
            FROM ({FUENTE_SIN_CONFLICTOS}) AS v
            LEFT JOIN {tabla} AS d
                ON d.Codigo_OBZ = v.code
            WHERE v.code IS NOT NULL
              AND v.name IS NOT NULL
              AND d.Codigo_OBZ IS NULL
        """)
    return cursor.fetchall()


def listar_operadores_retirados(cursor, tabla):
    """Operadores de flota.table_drivers que ya no aparecen en la vista de empleados."""
    cursor.execute(f"""
            SELECT
                d.Codigo_OBZ
            FROM {tabla} AS d
            LEFT JOIN [emoperation].[dbo].[em_view_employees] AS v
                ON v.code = d.Codigo_OBZ
            WHERE v.code IS NULL
        """)
    return cursor.fetchall()


def insertar_operador(cursor, tabla, codigo, nombre):
    cursor.execute(f"""
                INSERT INTO {tabla}
                    (Codigo_OBZ, Nombre_OBZ)
                VALUES (?, ?)
            """, codigo, nombre)


def eliminar_operador(cursor, tabla, codigo):
    """Borra el operador. Devuelve cuántas filas borró."""
    cursor.execute(f"""
                DELETE FROM {tabla}
                WHERE Codigo_OBZ = ?
            """, codigo)
    return cursor.rowcount


def actualizar_nombres(cursor, tabla):
    cursor.execute(f"""
            UPDATE d
            SET Nombre_OBZ = v.name
            FROM {tabla} AS d
            INNER JOIN ({FUENTE_SIN_CONFLICTOS}) AS v
                ON v.code = d.Codigo_OBZ
            WHERE v.name IS NOT NULL
              AND (d.Nombre_OBZ IS NULL OR d.Nombre_OBZ <> v.name)
        """)
    return cursor.rowcount


def validar_fuente(cursor):
    cursor.execute("""
        SELECT COUNT(*), COUNT(CASE WHEN nombres > 1 THEN 1 END)
        FROM (
            SELECT code, COUNT(DISTINCT name) AS nombres
            FROM [emoperation].[dbo].[em_view_employees]
            WHERE code IS NOT NULL AND name IS NOT NULL
            GROUP BY code
        ) AS fuente
    """)
    codigos, conflictos = cursor.fetchone()
    if not codigos:
        raise RuntimeError("La fuente de operadores está vacía.")
    return conflictos
