import re

from flask import Blueprint, render_template, request, flash, redirect, session
from config import connect
from werkzeug.security import generate_password_hash
from backend_security import login_required, requiere_permiso, validar_politica_password
from config import BASE_DIR
from logger import logger

Modulo_usuario = Blueprint(
    'Modulo_usuario',
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)

UFS_VALIDAS = {"10", "16", "TRANSVERSAL"}
PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PERMISO_EDITAR = 'Ingresar_asignar_permisos'


def _texto(campo):
    return (request.form.get(campo) or "").strip()


def _validar_datos_usuario(nombre, username, correo, uf, obligatorios):
    """Valida longitud y formato contra Table_usuarios. Los vacíos se aceptan si no son obligatorios."""
    if obligatorios and not all((nombre, username, correo, uf)):
        return 'Todos los campos son obligatorios.'
    if len(nombre) > 100:
        return 'El nombre no puede superar 100 caracteres.'
    if username and (len(username) > 50 or not re.fullmatch(r"[A-Za-z0-9._-]+", username)):
        return 'El usuario solo admite letras, números, punto, guion y guion bajo (máximo 50).'
    if correo and (len(correo) > 100 or not PATRON_EMAIL.match(correo)):
        return 'El correo no es válido.'
    if uf and uf not in UFS_VALIDAS:
        return 'La UF seleccionada no es válida.'
    return None


def _id_usuario_valido(id_usuario):
    return id_usuario.isascii() and id_usuario.isdecimal() and 0 < int(id_usuario) <= 2147483647


def _render():
    return render_template(
        'Front_usuarios.html',
        puede_editar=PERMISO_EDITAR in session.get('permisos', []),
    )


@Modulo_usuario.route('/', methods=['GET', 'POST'])
@login_required
@requiere_permiso('Ingresar_crear_usuario')
def crear_usuario():
    """Solo crea usuarios nuevos; nunca modifica una cuenta existente."""
    if request.method != 'POST':
        return _render()

    nombre = _texto('Nombre')
    id_usuario = _texto('IDusuario')
    username = _texto('username')
    password = request.form.get('password') or ''
    correo = _texto('Email')
    uf = _texto('UF')

    error = _validar_datos_usuario(nombre, username, correo, uf, obligatorios=True)
    if not error and not _id_usuario_valido(id_usuario):
        error = 'La identificación debe ser numérica.'
    if not error:
        error = validar_politica_password(password, username)
    if error:
        flash(error, 'error')
        return _render()

    conn = None
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM Table_usuarios WHERE IDusuario = ? OR Username = ?",
            (int(id_usuario), username)
        )
        if cursor.fetchone():
            flash('Ya existe un usuario con esa identificación o ese nombre de usuario. '
                  'Para modificarlo use la opción de edición.', 'error')
            return _render()

        # Quien crea la cuenta conoce la contraseña inicial: se obliga a cambiarla.
        cursor.execute(
            """INSERT INTO Table_usuarios
                   (Username, PasswordHash, Nombre, Email, Activo, IDusuario, UF, Cambio_password_obligatorio)
               VALUES (?, ?, ?, ?, 1, ?, ?, 1)""",
            (username, generate_password_hash(password), nombre, correo, int(id_usuario), uf)
        )
        conn.commit()
        logger.info("usuario_creado actor=%s usuario=%s", session.get('usuario'), username)
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("error_crear_usuario")
        flash('No fue posible crear el usuario.', 'error')
        return _render()
    finally:
        if conn:
            conn.close()

    flash('Usuario creado exitosamente. Deberá cambiar la contraseña en su primer ingreso.', 'success')
    return redirect('/Modulo_usuario/')


@Modulo_usuario.route('/editar', methods=['POST'])
@login_required
@requiere_permiso('Ingresar_crear_usuario')
@requiere_permiso(PERMISO_EDITAR)
def editar_usuario():
    """Modifica solo los campos diligenciados. No cambia el estado Activo.

    Exige el permiso de administración de permisos, porque cambiar la UF o la
    contraseña de otra cuenta equivale a administrar su acceso.
    """
    id_usuario = _texto('IDusuario')
    nombre = _texto('Nombre')
    username = _texto('username')
    correo = _texto('Email')
    uf = _texto('UF')
    password = request.form.get('password') or ''

    error = None if _id_usuario_valido(id_usuario) else 'La identificación debe ser numérica.'
    if not error:
        error = _validar_datos_usuario(nombre, username, correo, uf, obligatorios=False)
    if not error and password:
        error = validar_politica_password(password, username)
    if error:
        flash(error, 'error')
        return redirect('/Modulo_usuario/')

    # Contraseña temporal asignada por un administrador: se obliga a cambiarla.
    password_hash = generate_password_hash(password) if password else None
    cambios = {
        'Nombre': nombre or None,
        'Username': username or None,
        'Email': correo or None,
        'UF': uf or None,
        'PasswordHash': password_hash,
    }
    if not any(cambios.values()):
        flash('No se diligenció ningún campo para modificar.', 'error')
        return redirect('/Modulo_usuario/')

    conn = None
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("SELECT Username FROM Table_usuarios WHERE IDusuario = ?", (int(id_usuario),))
        actual = cursor.fetchone()
        if not actual:
            flash('No existe un usuario con esa identificación.', 'error')
            return redirect('/Modulo_usuario/')

        if username:
            cursor.execute(
                "SELECT 1 FROM Table_usuarios WHERE Username = ? AND IDusuario <> ?",
                (username, int(id_usuario))
            )
            if cursor.fetchone():
                flash('El nombre de usuario ya está asignado a otra persona.', 'error')
                return redirect('/Modulo_usuario/')

        # Los campos no diligenciados llegan como NULL y conservan su valor.
        cursor.execute("""
            UPDATE Table_usuarios
            SET Nombre = COALESCE(?, Nombre),
                Username = COALESCE(?, Username),
                Email = COALESCE(?, Email),
                UF = COALESCE(?, UF),
                PasswordHash = COALESCE(?, PasswordHash),
                Cambio_password_obligatorio = CASE WHEN ? IS NULL
                    THEN Cambio_password_obligatorio ELSE 1 END
            WHERE IDusuario = ?
        """, (nombre or None, username or None, correo or None, uf or None,
              password_hash, password_hash, int(id_usuario)))
        if cursor.rowcount != 1:
            raise ValueError('La edición no afectó exactamente un usuario.')
        conn.commit()
        campos_auditados = sorted(c for c, v in cambios.items() if v and c != 'PasswordHash')
        if password_hash:
            campos_auditados.append('Password_temporal')
        logger.info(
            "usuario_editado actor=%s usuario=%s campos=%s",
            session.get('usuario'), actual[0], ",".join(campos_auditados)
        )
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("error_editar_usuario")
        flash('No fue posible actualizar el usuario.', 'error')
        return redirect('/Modulo_usuario/')
    finally:
        if conn:
            conn.close()

    flash('Usuario actualizado correctamente.', 'success')
    return redirect('/Modulo_usuario/')
