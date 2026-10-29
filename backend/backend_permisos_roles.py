from flask import Blueprint, render_template, request, flash, redirect, jsonify
from config import connect
from backend_security import login_required, requiere_permiso
from config import BASE_DIR
from logger import logger

Modulo_permisos_roles = Blueprint(
    'Modulo_permisos_roles',
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)

@Modulo_permisos_roles.route('/', methods=['GET', 'POST'])
@login_required
@requiere_permiso('Ingresar_asignar_permisos')
def asignar_permisos():
    conn = connect()
    cursor = conn.cursor()

    # Traer usuarios y permisos existentes
    cursor.execute("SELECT ConsID, Nombre, Activo FROM Table_usuarios")
    users = cursor.fetchall()

    cursor.execute("SELECT PermisoID, Nombre FROM Table_permisos")
    permisos = cursor.fetchall()

    if request.method == 'POST':
        user_id = request.form.get('user')
        permisos_ids = request.form.getlist('permisos')
        activo = request.form.get('activo')

        if not user_id:
            flash('Primero debe seleccionar un usuario', 'error')
            conn.close()
            return redirect('/Modulo_permisos_roles/')
        if activo not in ('0', '1'):
            flash('El estado seleccionado no es válido', 'error')
            conn.close()
            return redirect('/Modulo_permisos_roles/')
        activo = int(activo)

        try:
            cursor.execute("UPDATE Table_usuarios SET Activo = ? WHERE ConsID = ?", (activo, user_id))
            if cursor.rowcount != 1:
                raise ValueError('El usuario seleccionado no existe.')

            # Primero eliminar permisos anteriores del rol
            cursor.execute("DELETE FROM Table_usuarios_permisos WHERE UserID = ?", user_id)

            # Insertar nuevos permisos
            for pid in permisos_ids:
                cursor.execute("INSERT INTO Table_usuarios_permisos (UserID, PermisoID) VALUES (?, ?)", user_id, pid)
            conn.commit()
            flash('Permisos y estado actualizados correctamente', 'success')
        except Exception:
            conn.rollback()
            logger.exception("error_actualizar_permisos")
            flash('No fue posible actualizar los permisos y el estado', 'error')
        finally:
            conn.close()
        return redirect('/Modulo_permisos_roles/')

    conn.close()
    return render_template('Front_permisos_roles.html', users=users, permisos=permisos)


@Modulo_permisos_roles.route('/eliminar_usuario', methods=['POST'])
@login_required
@requiere_permiso('Ingresar_asignar_permisos')
def eliminar_usuario():
    """Elimina al usuario seleccionado y sus permisos en una transacción."""
    user_id = request.form.get('user')
    if not user_id:
        flash('Primero debe seleccionar un usuario', 'error')
        return redirect('/Modulo_permisos_roles/')

    conn = connect()
    cursor = conn.cursor()
    try:

        cursor.execute("DELETE FROM Table_password_reset WHERE UserId = ?", user_id)
        cursor.execute("DELETE FROM Table_usuarios_permisos WHERE UserID = ?", user_id)
        cursor.execute("DELETE FROM Table_usuarios WHERE ConsID = ?", user_id)
        if cursor.rowcount != 1:
            raise ValueError('El usuario seleccionado no existe.')
        conn.commit()
        flash('Usuario y permisos asociados eliminados correctamente', 'success')
    except Exception:
        conn.rollback()
        # El detalle técnico va al log; al usuario, un mensaje genérico.
        logger.exception("error_eliminar_usuario")
        flash('No fue posible eliminar el usuario.', 'error')
    finally:
        conn.close()

    return redirect('/Modulo_permisos_roles/')


@Modulo_permisos_roles.route('/permisos_usuario/<int:user_id>')
@login_required
@requiere_permiso('Ingresar_asignar_permisos')
def permisos_usuario(user_id):
    """Devuelve los permisos asignados al usuario seleccionado."""
    conn = connect()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT UserID, PermisoID FROM Table_usuarios_permisos WHERE UserID = ?",
            user_id
        )
        permisos_ids = [fila[1] for fila in cursor.fetchall()]
        return jsonify({"permisos": permisos_ids})
    finally:
        conn.close()


def _actualizar_obligacion_cambio_password(valor, mensaje_exito):
    user_ids = list(dict.fromkeys(request.form.getlist('user_ids')))
    if not user_ids:
        flash('Debe seleccionar al menos un usuario.', 'error')
        return redirect('/Modulo_permisos_roles/')

    if any(not user_id.isdecimal() or int(user_id) <= 0 for user_id in user_ids):
        flash('La selección de usuarios no es válida.', 'error')
        return redirect('/Modulo_permisos_roles/')

    conn = None
    try:
        conn = connect()
        cursor = conn.cursor()
        for user_id in user_ids:
            cursor.execute(
                "UPDATE Table_usuarios SET Cambio_password_obligatorio = ? WHERE ConsID = ?",
                (valor, int(user_id))
            )
            if cursor.rowcount != 1:
                raise ValueError('No se encontró un usuario de la selección.')
        conn.commit()
        flash(mensaje_exito, 'success')
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("error_actualizar_cambio_password_obligatorio")
        flash('No fue posible actualizar la obligación de cambio de contraseña.', 'error')
    finally:
        if conn:
            conn.close()

    return redirect('/Modulo_permisos_roles/')


@Modulo_permisos_roles.route('/forzar_cambio_password', methods=['POST'])
@login_required
@requiere_permiso('Ingresar_asignar_permisos')
def forzar_cambio_password():
    return _actualizar_obligacion_cambio_password(
        1,
        'Se solicitó el cambio obligatorio de contraseña para los usuarios seleccionados.'
    )


@Modulo_permisos_roles.route('/quitar_cambio_password', methods=['POST'])
@login_required
@requiere_permiso('Ingresar_asignar_permisos')
def quitar_cambio_password():
    return _actualizar_obligacion_cambio_password(
        0,
        'Se quitó la obligación de cambio de contraseña para los usuarios seleccionados.'
    )

