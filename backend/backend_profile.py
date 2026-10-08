from flask import Blueprint, flash, redirect, url_for, render_template, session, request, jsonify, send_from_directory, send_file, abort, url_for
import os
from mimetypes import guess_type
from config import connect
from datetime import datetime
from backend_security import login_required, requiere_permiso
from werkzeug.security import generate_password_hash, check_password_hash
from config import BASE_DIR
from logger import logger


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
    conn = connect()
    cursor = conn.cursor()
    
    query_main = """ 
            SELECT Username, Nombre, Email, FechaCreacion, Activo, IDusuario, UF
            FROM Table_usuarios
            WHERE Username = ?
    """ 
    cursor.execute(query_main, (usuario_logeado,)) 
    columns = [column[0] for column in cursor.description] 
    row = cursor.fetchone()
    conn.close()

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

    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT PasswordHash FROM Table_usuarios WHERE Username = ?", (current_user,))
    row = cursor.fetchone()
    
    if row and check_password_hash(row[0], old_password):
        nuevo_hash = generate_password_hash(new_password)
        try:
            cursor.execute("""
                UPDATE Table_usuarios
                SET PasswordHash = ?, Cambio_password_obligatorio = 0
                WHERE Username = ?
            """, (nuevo_hash, current_user))
            if cursor.rowcount != 1:
                conn.rollback()
                return jsonify({'status': 'error', 'message': 'No fue posible actualizar la contraseña.'}), 500
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("error_cambiar_password_perfil")
            return jsonify({'status': 'error', 'message': 'No fue posible actualizar la contraseña.'}), 500
        finally:
            conn.close()
        return jsonify({'status': 'success', 'message': 'Contraseña actualizada con éxito.'})
    
    conn.close()
    return jsonify({'status': 'error', 'message': 'La contraseña actual es incorrecta.'})
