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

        operadores_nuevos = cursor.fetchall()

        return operadores_nuevos

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


def sincronizar_operadores():

    operadores_nuevos = obtener_operadores_nuevos()

    nuevos = insertar_operadores_nuevos(operadores_nuevos)

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

    return nuevos, existentes


