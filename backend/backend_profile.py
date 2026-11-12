from repositories.sesiones import sesion_bd
from contextlib import closing
from flask import Blueprint, render_template, session, request, jsonify
from config import connect
from modelos import usuarios as modelo_usuarios
from backend_security import login_required, validar_politica_password
from werkzeug.security import generate_password_hash, check_password_hash
from config import BASE_DIR
from logger import logger, contexto_peticion


Profile = Blueprint(
    'Profile',               # nombre interno del blueprint
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)


# --- RUTA PRINCIPAL (MOSTRAR PERFIL) ---
@Profile.route('/')
@login_required
def index():
    usuario_logeado = session.get('usuario')
    mostrar_alerta_cambio_password = session.pop('mostrar_alerta_cambio_password', False)
    with sesion_bd(connect) as conn:
        with closing(conn.cursor()) as cursor:
            columns, row = modelo_usuarios.buscar_perfil(cursor, usuario_logeado)

    if not row:
        return "Usuario no encontrado", 404

    registro = dict(zip(columns, row))
    return render_template(
        "Front_profile.html",
        registro=registro,
        mostrar_alerta_cambio_password=mostrar_alerta_cambio_password
    )

# --- RUTA PARA PROCESAR EL CAMBIO (AJAX) ---
@Profile.route('/cambiar-password', methods=['POST'])
@login_required
def cambiar_password():
    current_user = session.get('usuario')
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Validaciones básicas
    if not old_password or not new_password:
        return jsonify({'status': 'error', 'message': 'Faltan datos.'})

    if new_password != confirm_password:
        return jsonify({'status': 'error', 'message': 'Las nuevas contraseñas no coinciden.'})

    error = validar_politica_password(new_password, current_user)
    if error:
        return jsonify({'status': 'error', 'message': error})

    with sesion_bd(connect) as conn:
        with closing(conn.cursor()) as cursor:
            row = modelo_usuarios.buscar_hash_contrasena(cursor, current_user)

            if row and check_password_hash(row[0], old_password):
                nuevo_hash = generate_password_hash(new_password)
                try:
                    filas_actualizadas = modelo_usuarios.cambiar_hash_contrasena(
                        cursor, nuevo_hash, current_user
                    )
                    if filas_actualizadas != 1:
                        conn.rollback()
                        return jsonify({'status': 'error', 'message': 'No fue posible actualizar la contraseña.'}), 500
                    conn.commit()
                    logger.info("cambio_contrasena_perfil %s", contexto_peticion())
                except Exception:
                    conn.rollback()
                    logger.exception("error_cambiar_password_perfil %s", contexto_peticion())
                    return jsonify({'status': 'error', 'message': 'No fue posible actualizar la contraseña.'}), 500
                return jsonify({'status': 'success', 'message': 'Contraseña actualizada con éxito.'})

    logger.warning("cambio_contrasena_perfil_rechazado %s", contexto_peticion())
    return jsonify({'status': 'error', 'message': 'La contraseña actual es incorrecta.'})
