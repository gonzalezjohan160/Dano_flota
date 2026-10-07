from config import connect


def obtener_operadores_nuevos():

    conexion = connect()
    cursor = conexion.cursor()

    try:

        cursor.execute("""
            SELECT
                v.code,
                v.name
            FROM [emoperation].[dbo].[em_view_employees] AS v
            LEFT JOIN [damage_to_fleet].[dbo].[table_drivers] AS d
                ON d.Codigo_OBZ = v.code
            WHERE v.code IS NOT NULL
              AND v.name IS NOT NULL
              AND d.Codigo_OBZ IS NULL
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        conexion.close()


def obtener_operadores_eliminar():

    conexion = connect()
    cursor = conexion.cursor()

    try:

        cursor.execute("""
            SELECT
                d.Codigo_OBZ
            FROM [damage_to_fleet].[dbo].[table_drivers] AS d
            LEFT JOIN [emoperation].[dbo].[em_view_employees] AS v
                ON v.code = d.Codigo_OBZ
            WHERE v.code IS NULL
        """)

        return cursor.fetchall()

    finally:
        cursor.close()
        conexion.close()


def insertar_operadores_nuevos(operadores):

    conexion = connect()
    cursor = conexion.cursor()

    nuevos = 0

    try:

        for operador in operadores:

            code = operador.code
            nombre = operador.name

            cursor.execute("""
                INSERT INTO [damage_to_fleet].[dbo].[table_drivers]
                    (Codigo_OBZ, Nombre_OBZ)
                VALUES (?, ?)
            """, code, nombre)

            nuevos += 1

        conexion.commit()

        return nuevos

    except Exception:

        conexion.rollback()
        raise

    finally:

        cursor.close()
        conexion.close()


def eliminar_operadores(operadores):

    conexion = connect()
    cursor = conexion.cursor()

    eliminados = 0

    try:

        for operador in operadores:

            code = operador.Codigo_OBZ

            cursor.execute("""
                DELETE FROM [damage_to_fleet].[dbo].[table_drivers]
                WHERE Codigo_OBZ = ?
            """, code)

            eliminados += cursor.rowcount

        conexion.commit()

        return eliminados

    except Exception:

        conexion.rollback()
        raise

    finally:

        cursor.close()
        conexion.close()


def sincronizar_operadores():

    operadores_nuevos = obtener_operadores_nuevos()
    operadores_eliminar = obtener_operadores_eliminar()

    nuevos = insertar_operadores_nuevos(operadores_nuevos)
    eliminados = eliminar_operadores(operadores_eliminar)

    conexion = connect()
    cursor = conexion.cursor()

    try:

        cursor.execute("""
            SELECT COUNT(*)
            FROM [emoperation].[dbo].[em_view_employees]
            WHERE code IS NOT NULL
              AND name IS NOT NULL
        """)

        total_operadores = cursor.fetchone()[0]

    finally:

        cursor.close()
        conexion.close()

    existentes = total_operadores - nuevos

    return nuevos, eliminados, existentes