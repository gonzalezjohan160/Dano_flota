"""Consultas de usuarios, permisos y datos básicos del perfil.

Las funciones reciben un cursor abierto y no dependen de Flask. Las transacciones
las controla el controlador que llama a cada consulta.

Los usuarios no se borran: se inactivan (activo = 0). ConsID es la clave
referenciada por los autores de casos y gestiones.
"""


def existe_usuario(cursor, identificacion, nombre_usuario):
    cursor.execute(
        "SELECT 1 FROM usuario.Table_usuarios WHERE IDusuario = ? OR Username = ?",
        (identificacion, nombre_usuario),
    )
    return cursor.fetchone() is not None


def crear_usuario(cursor, nombre_usuario, hash_contrasena, nombre, correo, identificacion, uf):
    cursor.execute(
        """INSERT INTO usuario.Table_usuarios
               (Username, PasswordHash, Nombre, Email, Activo, IDusuario, Alcance_UF,
                Cambio_password_obligatorio)
           VALUES (?, ?, ?, ?, 1, ?, ?, 1)""",
        (nombre_usuario, hash_contrasena, nombre, correo, identificacion, uf),
    )


def buscar_usuario_por_identificacion(cursor, identificacion):
    cursor.execute(
        "SELECT Username FROM usuario.Table_usuarios WHERE IDusuario = ?",
        (identificacion,),
    )
    return cursor.fetchone()


def buscar_nombre_por_id(cursor, usuario_id):
    """Nombre visible para auditoria; la referencia persistida sigue siendo ConsID."""
    cursor.execute("SELECT Username FROM usuario.Table_usuarios WHERE ConsID = ?", (usuario_id,))
    fila = cursor.fetchone()
    return fila[0] if fila else None


def existe_nombre_en_otro_usuario(cursor, nombre_usuario, identificacion):
    cursor.execute(
        "SELECT 1 FROM usuario.Table_usuarios WHERE Username = ? AND IDusuario <> ?",
        (nombre_usuario, identificacion),
    )
    return cursor.fetchone() is not None


def actualizar_usuario(
    cursor, nombre, nombre_usuario, correo, uf, hash_contrasena, identificacion
):
    """Actualiza el perfil; las FK a ConsID permanecen y las vistas muestran el nombre actual."""
    cursor.execute("""
        UPDATE usuario.Table_usuarios
        SET Nombre = COALESCE(?, Nombre),
            Username = COALESCE(?, Username),
            Email = COALESCE(?, Email),
            Alcance_UF = COALESCE(?, Alcance_UF),
            PasswordHash = COALESCE(?, PasswordHash),
            Cambio_password_obligatorio = CASE WHEN ? IS NULL
                THEN Cambio_password_obligatorio ELSE 1 END
        WHERE IDusuario = ?
    """, (
        nombre, nombre_usuario, correo, uf, hash_contrasena,
        hash_contrasena, identificacion,
    ))
    return cursor.rowcount


def listar_usuarios(cursor):
    cursor.execute("SELECT ConsID, Nombre, Activo FROM usuario.Table_usuarios")
    return cursor.fetchall()


def listar_permisos(cursor):
    cursor.execute("SELECT PermisoID, Nombre FROM usuario.Table_permisos")
    return cursor.fetchall()


def buscar_permisos_usuario(cursor, id_usuario):
    cursor.execute(
        "SELECT UserID, PermisoID FROM usuario.Table_usuarios_permisos WHERE UserID = ?",
        id_usuario,
    )
    return cursor.fetchall()


def actualizar_estado_usuario(cursor, activo, id_usuario):
    cursor.execute(
        "UPDATE usuario.Table_usuarios SET Activo = ? WHERE ConsID = ?",
        (activo, id_usuario),
    )
    return cursor.rowcount


def eliminar_permisos_usuario(cursor, id_usuario):
    cursor.execute("DELETE FROM usuario.Table_usuarios_permisos WHERE UserID = ?", id_usuario)


def insertar_permiso_usuario(cursor, id_usuario, id_permiso):
    cursor.execute(
        "INSERT INTO usuario.Table_usuarios_permisos (UserID, PermisoID) VALUES (?, ?)",
        id_usuario,
        id_permiso,
    )


def actualizar_obligacion_contrasena(cursor, valor, id_usuario):
    cursor.execute(
        "UPDATE usuario.Table_usuarios SET Cambio_password_obligatorio = ? WHERE ConsID = ?",
        (valor, id_usuario),
    )
    return cursor.rowcount


def buscar_perfil(cursor, nombre_usuario):
    """(columnas, fila) del perfil, con los nombres que usa la plantilla."""
    cursor.execute("""
        SELECT Username AS Username, Nombre AS Nombre, Email AS Email,
               FechaCreacion AS FechaCreacion, Activo AS Activo,
               IDusuario AS IDusuario, Alcance_UF AS UF
        FROM usuario.Table_usuarios
        WHERE Username = ?
    """, (nombre_usuario,))
    columnas = [columna[0] for columna in cursor.description]
    return columnas, cursor.fetchone()


def buscar_hash_contrasena(cursor, nombre_usuario):
    cursor.execute(
        "SELECT PasswordHash FROM usuario.Table_usuarios WHERE Username = ?",
        (nombre_usuario,),
    )
    return cursor.fetchone()


def cambiar_hash_contrasena(cursor, hash_contrasena, nombre_usuario):
    cursor.execute("""
        UPDATE usuario.Table_usuarios
        SET PasswordHash = ?, Cambio_password_obligatorio = 0
        WHERE Username = ?
    """, (hash_contrasena, nombre_usuario))
    return cursor.rowcount
