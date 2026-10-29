import hashlib
import os
from flask import session, abort, redirect, url_for, request
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Límite de intentos (login y recuperación). Con varios workers de Gunicorn el
# almacenamiento en memoria es por proceso; para un límite compartido configure
# RATELIMIT_STORAGE_URI (por ejemplo redis://localhost:6379).
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)
LIMITE_INTENTOS_LOGIN = "5 per minute"
# Muchos usuarios salen por la misma IP pública de la empresa: el límite por IP
# es más amplio para no bloquear a toda una sede por errores de varias personas.
LIMITE_INTENTOS_IP = "20 per minute"


def usuario_del_formulario():
    """Clave del límite por usuario: el nombre digitado en el login."""
    return "usuario:" + (request.form.get("username") or "").strip().lower()


def hash_token_restablecimiento(token):
    """En la base solo se guarda el SHA-256 del token, nunca el token en claro."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

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


# Los documentos que carga Relaciones Laborales (debido proceso) solo los ve RRLL.
PERMISO_ADJUNTOS_LABORALES = "Ingresar_modulo__laboral"


def puede_ver_adjuntos_laborales():
    return PERMISO_ADJUNTOS_LABORALES in session.get("permisos", [])


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

        # Se anota el permiso para comprobar que coincide con el mapa central
        # de autorizacion.py (los decoradores son la segunda barrera).
        decorated_function.permisos_requeridos = getattr(f, "permisos_requeridos", ()) + (permiso,)
        return decorated_function
    return decorator



def normalizar_uf_sesion(uf):
    """UF tal como se guarda en la sesión ("0" cuando el usuario no tiene)."""
    return str(uf).strip() if uf else "0"


def cargar_permisos(usuario_id, cursor=None):
    """
    Consulta la base de datos y devuelve la lista de permisos del usuario.
    Si se pasa un cursor se reutiliza su conexión y no se cierra.
    """
    if cursor is not None:
        return _consultar_permisos(cursor, usuario_id)

    from config import connect

    conn = connect()
    try:
        return _consultar_permisos(conn.cursor(), usuario_id)
    finally:
        conn.close()


def _consultar_permisos(cursor, usuario_id):
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

    return [row[0] for row in cursor.fetchall()]
