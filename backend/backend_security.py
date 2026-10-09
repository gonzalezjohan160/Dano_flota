from flask import session, abort, redirect, url_for
from functools import wraps

UFS_AUTORIZADAS = {"10", "16"}


def ufs_autorizadas_sesion():
    """Devuelve las UF que puede consultar la sesión según la regla vigente."""
    uf_usuario = session.get("UF")
    if uf_usuario == "TRANSVERSAL":
        return (10, 16)

    uf_normalizada = str(uf_usuario).strip() if uf_usuario is not None else ""
    if uf_normalizada not in UFS_AUTORIZADAS:
        return ()
    return (int(uf_normalizada),)


def usuario_puede_acceder_uf(uf_registro):
    """Valida acceso a una UF; UF ausente o fuera del conjunto permitido deniega."""
    if uf_registro is None:
        return False
    uf_normalizada = str(uf_registro).strip()
    return uf_normalizada in {str(uf) for uf in ufs_autorizadas_sesion()}


LONGITUD_MINIMA_PASSWORD = 10


def validar_politica_password(password, username=None):
    """Devuelve el motivo de rechazo, o None si la contraseña cumple la política."""
    password = password or ""
    if len(password) < LONGITUD_MINIMA_PASSWORD:
        return f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres."
    if not any(c.islower() for c in password) or not any(c.isupper() for c in password):
        return "La contraseña debe combinar mayúsculas y minúsculas."
    if not any(c.isdigit() for c in password):
        return "La contraseña debe incluir al menos un número."
    if username and username.strip().lower() in password.lower():
        return "La contraseña no puede contener el nombre de usuario."
    return None


def login_required(f):
    """
    Decorador para obligar a que el usuario haya iniciado sesión.
    Si no, lo redirige a /login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('Modulo_login.login'))
        return f(*args, **kwargs)
    return decorated_function

def requiere_permiso(permiso):
    """
    Decorador que valida que el usuario tenga un permiso específico.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):

            if 'usuario' not in session:
                return redirect(url_for('Modulo_login.login'))

            permisos = session.get('permisos', [])

            if permiso not in permisos:
                abort(403)

            return f(*args, **kwargs)

        return decorated_function
    return decorator



def cargar_permisos(usuario_id):
    """
    Consulta la base de datos y devuelve la lista de permisos del usuario.
    """
    from config import connect

    conn = connect()
    cursor = conn.cursor()

    # Traer permisos directamente del usuario
    cursor.execute("""
        SELECT p.Nombre
        FROM Table_permisos p
        INNER JOIN Table_usuarios_permisos up
            ON p.PermisoID = up.PermisoID
        INNER JOIN Table_usuarios u
            ON u.ConsID = up.UserID
        WHERE u.Username = ?
    """, usuario_id)

    permisos = [row[0] for row in cursor.fetchall()]
    conn.close()
    return permisos
