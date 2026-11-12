"""Consultas de autenticación: inicio de sesión, sesión en curso, permisos y
recuperación de contraseña.

Los tokens de recuperación nunca llegan aquí en claro: el controlador guarda y
busca solo su huella SHA-256 (hash_token_restablecimiento).
"""


# --------------------------------------------------------- inicio de sesión ---

def buscar_usuario_para_login(cursor, nombre_usuario):
    
    cursor.execute("""
                SELECT ConsID, PasswordHash, Alcance_UF, Activo,
                       Cambio_password_obligatorio, Username
                FROM usuario.Table_usuarios
                WHERE Username = ?
            """, nombre_usuario)
    return cursor.fetchone()


# ------------------------------------------------- sesión en curso ---

def buscar_estado_de_sesion(cursor, identificador):
    """Actualiza la sesion; acepta Username de cookies anteriores para migrarlas."""
    campo = "ConsID" if type(identificador) is int else "Username"
    cursor.execute(
        f"SELECT Activo, Alcance_UF, Cambio_password_obligatorio, ConsID, Username FROM usuario.Table_usuarios WHERE {campo} = ?",
        identificador,
    )
    return cursor.fetchone()


def buscar_permisos(cursor, usuario_id):
    """Permisos por la FK numerica existente de usuario_permiso."""
    cursor.execute("""
        SELECT p.Nombre
        FROM usuario.Table_permisos as p
        INNER JOIN usuario.Table_usuarios_permisos as up ON p.PermisoID = up.PermisoID
        WHERE up.UserID = ?
    """, usuario_id)
    return [row[0] for row in cursor.fetchall()]


# ------------------------------------------- solicitud de recuperación ---

def buscar_id_por_correo(cursor, correo):
    """Fila (ConsId,) del usuario con ese correo, o None."""
    cursor.execute("SELECT ConsID FROM usuario.Table_usuarios WHERE Email = ?", correo)
    return cursor.fetchone()


def anular_enlaces_pendientes(cursor, id_usuario):
    """Marca como usados los enlaces aún vigentes del usuario (un enlace nuevo anula los anteriores)."""
    cursor.execute("""
                    UPDATE usuario.Table_password_reset
                    SET Used = 1
                    WHERE UserId = ? AND Used = 0
                """, (id_usuario,))


def purgar_enlaces_sin_uso(cursor, ahora):
    """Borra los enlaces vencidos, usados o anulados (BD-8)."""
    cursor.execute("""
                DELETE FROM usuario.Table_password_reset
                WHERE Expiration < ? OR Used = 1
            """, (ahora,))


def guardar_enlace(cursor, id_usuario, token, expiracion):
    """Guarda un enlace nuevo con la huella SHA-256 del token (nunca el token)."""
    cursor.execute("""
                    INSERT INTO usuario.Table_password_reset (UserId, Token, Expiration)
                    VALUES (?, ?, ?)
                """, (id_usuario, token, expiracion))


# --------------------------------------------------------- restablecimiento ---

def buscar_enlace(cursor, token):
    """Fila (usuario_id, vence, usado, nombre_usuario) del enlace con esa huella, o None."""
    cursor.execute("""
            SELECT r.UserId, r.Expiration, r.Used, u.Username
            FROM usuario.Table_password_reset as r
            INNER JOIN usuario.Table_usuarios as  u ON u.ConsID = r.UserId
            WHERE r.Token = ?
        """, token)
    return cursor.fetchone()


def reclamar_enlace(cursor, token, ahora):
    """Marca el enlace como usado solo si sigue vigente y sin usar.

    Devuelve cuántas filas cambió: 1 si este pedido lo reclamó; 0 si otro pedido
    lo usó antes o ya venció (impide el uso concurrente del mismo enlace).
    """
    cursor.execute("""
                UPDATE usuario.Table_password_reset
                SET Used = 1
                WHERE token = ? AND Used = 0 AND Expiration >= ?
            """, (token, ahora))
    return cursor.rowcount


def cambiar_contrasena(cursor, hash_contrasena, id_usuario):
    """Guarda el hash de la contraseña nueva. Devuelve cuántas filas cambió."""
    cursor.execute("""
                UPDATE usuario.Table_usuarios
                SET PasswordHash = ?
                WHERE ConsId = ?
            """, (hash_contrasena, id_usuario))
    return cursor.rowcount
