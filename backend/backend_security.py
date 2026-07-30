from flask import session, abort, redirect, url_for
from functools import wraps

def login_required(f):
    """
    Decorador para obligar a que el usuario haya iniciado sesión.
    Si no, lo redirige a /login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("[AUTH] claves de sesión:", list(session.keys()))
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
