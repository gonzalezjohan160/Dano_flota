from repositories.sesiones import sesion_bd
from contextlib import closing
from flask import Blueprint, render_template, request, flash, redirect, jsonify
from config import connect
from modelos import usuarios as modelo_usuarios
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
    with sesion_bd(connect) as conn:
        with closing(conn.cursor()) as cursor:
            # Traer usuarios y permisos existentes
            users = modelo_usuarios.listar_usuarios(cursor)
            permisos = modelo_usuarios.listar_permisos(cursor)

            if request.method == 'POST':
                user_id = request.form.get('user')
                permisos_ids = request.form.getlist('permisos')
                activo = request.form.get('activo')

                if not user_id:
                    flash('Primero debe seleccionar un usuario', 'error')
                    return redirect('/Modulo_permisos_roles/')
                if activo not in ('0', '1'):
                    flash('El estado seleccionado no es válido', 'error')
                    return redirect('/Modulo_permisos_roles/')
                activo = int(activo)

                try:
                    filas_actualizadas = modelo_usuarios.actualizar_estado_usuario(
                        cursor, activo, user_id
                    )
                    if filas_actualizadas != 1:
                        raise ValueError('El usuario seleccionado no existe.')

                    # Primero eliminar permisos anteriores del rol
                    modelo_usuarios.eliminar_permisos_usuario(cursor, user_id)

                    # Insertar nuevos permisos
                    for id_permiso in permisos_ids:
                        modelo_usuarios.insertar_permiso_usuario(cursor, user_id, id_permiso)
                    conn.commit()
                    flash('Permisos y estado actualizados correctamente', 'success')
                except Exception:
                    conn.rollback()
                    logger.exception("error_actualizar_permisos")
                    flash('No fue posible actualizar los permisos y el estado', 'error')
                return redirect('/Modulo_permisos_roles/')

    return render_template('Front_permisos_roles.html', users=users, permisos=permisos)


@Modulo_permisos_roles.route('/permisos_usuario/<int:user_id>')
@login_required
@requiere_permiso('Ingresar_asignar_permisos')
def permisos_usuario(user_id):
    """Devuelve los permisos asignados al usuario seleccionado."""
    with sesion_bd(connect) as conn:
        with closing(conn.cursor()) as cursor:
            filas = modelo_usuarios.buscar_permisos_usuario(cursor, user_id)
            permisos_ids = [fila[1] for fila in filas]
        return jsonify({"permisos": permisos_ids})


def _actualizar_obligacion_cambio_password(valor, mensaje_exito):
    user_ids = list(dict.fromkeys(request.form.getlist('user_ids')))
    if not user_ids:
        flash('Debe seleccionar al menos un usuario.', 'error')
        return redirect('/Modulo_permisos_roles/')

    if any(not user_id.isdecimal() or int(user_id) <= 0 for user_id in user_ids):
        flash('La selección de usuarios no es válida.', 'error')
        return redirect('/Modulo_permisos_roles/')

    try:
        with sesion_bd(connect, transaccional=True) as conn:
            with closing(conn.cursor()) as cursor:
                for user_id in user_ids:
                    filas_actualizadas = modelo_usuarios.actualizar_obligacion_contrasena(
                        cursor, valor, int(user_id)
                    )
                    if filas_actualizadas != 1:
                        raise ValueError('No se encontró un usuario de la selección.')
        flash(mensaje_exito, 'success')
    except Exception:
        logger.exception("error_actualizar_cambio_password_obligatorio")
        flash('No fue posible actualizar la obligación de cambio de contraseña.', 'error')
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

