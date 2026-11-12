"""Consultas de los tutoriales; no accede a Flask ni al sistema de archivos."""


def listar_tutoriales(cursor):
    cursor.execute("""
        SELECT id, Titulo
        FROM usuario.table_tutoriales
        ORDER BY Fecha_subida DESC, id DESC
    """)
    return cursor.fetchall()


def crear_tutorial(cursor, titulo, nombre_archivo, ruta_archivo):
    cursor.execute("""
        INSERT INTO usuario.table_tutoriales
            (Titulo, FileName, FilePath)
        VALUES (?, ?, ?)
    """, titulo, nombre_archivo, ruta_archivo)


def buscar_archivo_tutorial(cursor, id_tutorial):
    """Consulta compartida por las rutas que eliminan y reproducen un video."""
    cursor.execute("""
        SELECT FileName, FilePath
        FROM usuario.table_tutoriales
        WHERE id = ?
    """, id_tutorial)
    return cursor.fetchone()


def eliminar_tutorial(cursor, id_tutorial):
    cursor.execute("""
        DELETE FROM usuario.table_tutoriales
        WHERE id = ?
    """, id_tutorial)
