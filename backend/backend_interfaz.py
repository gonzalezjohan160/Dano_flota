from flask import Flask, app, render_template, request, jsonify, send_from_directory, send_file, url_for, abort, redirect,session
import os
from mimetypes import guess_type
from config import connect
from datetime import datetime,timedelta
from backend_unificado import Modulo_unificado
from backend_dashboard import Front_dashboard
from backend_usuarios import Modulo_usuario
from backend_permisos_roles import Modulo_permisos_roles
from backend_login import Modulo_login
from backend_historico_movil import Historico_movil
from backend_capturador import Capturador
from backend_reparaciones import Capturador_rep
from backend_historico_danos import Historico_danos
from backend_profile import Profile
from backend_tutoriales import Tutoriales
from pathlib import Path
from sincronizar_operadores import sincronizar_operadores
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from logger import logger

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

Interfaz = Flask(
    __name__,
    template_folder=str(BASE_DIR / "frontend"),
    static_folder=str(BASE_DIR / "Static")
)

csrf = CSRFProtect()
csrf.init_app(Interfaz)

Interfaz.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=60)
Interfaz.config["SESSION_REFRESH_EACH_REQUEST"] = True
Interfaz.config["SESSION_COOKIE_HTTPONLY"] = True
Interfaz.config["SESSION_COOKIE_SAMESITE"] = "Lax"

Interfaz.secret_key = os.environ["SECRET_KEY"]

@Interfaz.before_request
def proteger_rutas():
    rutas_publicas = {
        'Modulo_login.login',
        'Modulo_login.forgot_password',
        'Modulo_login.reset_password',
    }

    # Permitir únicamente los archivos estáticos propios de Flask
    if request.endpoint and (
        request.endpoint == 'static' or
        request.endpoint.endswith('.static')
    ):          
        return

    # Permitir las rutas públicas de autenticación
    if request.endpoint in rutas_publicas:
        return

    # Todo lo demás requiere sesión
    if 'usuario' not in session:
        return redirect(url_for('Modulo_login.login'))

    # La ruta de cambio y el cierre de sesión siguen permitidos aunque haya
    # una obligación pendiente. Profile.index consulta el estado para notificar
    # al frontend y permite mostrar la pantalla de cambio.
    if request.endpoint in {
        'Profile.cambiar_password',
        'Modulo_login.logout',
    }:
        return

    # Se consulta el estado actual para que también aplique a sesiones ya abiertas.
    conn = None
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ISNULL(Cambio_password_obligatorio, 0) FROM Table_usuarios WHERE Username = ?",
            session.get('usuario_id')
        )
        estado_cambio = cursor.fetchone()
    except Exception:
        logger.exception("error_verificar_cambio_password_obligatorio")
        abort(503)
    finally:
        if conn:
            conn.close()

    if estado_cambio and estado_cambio[0]:
        session['mostrar_alerta_cambio_password'] = True
        if request.endpoint != 'Profile.index':
            return redirect(url_for('Profile.index'))

Interfaz.register_blueprint(Modulo_login)

# Registrar profile como Blueprint
Interfaz.register_blueprint(Profile, url_prefix='/Profile')

# Registrar Capturador como Blueprint
Interfaz.register_blueprint(Capturador, url_prefix='/Capturador')

# Registrar Modulo_unificado como Blueprint
# Expone /Operaciones, /Mantenimiento, /SeguridadVial y /RelacionesLaborales
Interfaz.register_blueprint(Modulo_unificado, url_prefix='')

# Registrar Dashboard como Blueprint
Interfaz.register_blueprint(Front_dashboard, url_prefix='/Dashboard')

# Registrar Usuarios como Blueprint
Interfaz.register_blueprint(Modulo_usuario, url_prefix='/Modulo_usuario')

# Registrar roles como Blueprint
Interfaz.register_blueprint(Modulo_permisos_roles, url_prefix='/Modulo_permisos_roles')

# Registrar Historico_moviles como Blueprint
Interfaz.register_blueprint(Historico_movil, url_prefix='/Historico_movil')

# Registrar Capturador de reparaciones como Blueprint
Interfaz.register_blueprint(Capturador_rep, url_prefix='/Capturador_rep')

# Registrar Historico de daños como Blueprint
Interfaz.register_blueprint(Historico_danos, url_prefix='/Historico_danos')

# Registrar Tutoriales
Interfaz.register_blueprint(Tutoriales, url_prefix='/Videos')

@Interfaz.route('/interfaz')
def index():
    """Redirige a Dashboard al cargar la página raíz"""
    return redirect('/Dashboard')


@Interfaz.errorhandler(404)
@Interfaz.errorhandler(403)
def page_not_found(e):
    # Verificamos si existe la clave 'usuario' en la sesión
    if 'usuario' in session:
        # Si está logeado, lo mandamos al dashboard (interfaz)
        return redirect('/interfaz') 
    else:
        # Si no está logeado, al login
        return redirect(url_for('Modulo_login.login'))



if __name__ == "__main__":
        # Ejemplo: Limitar a 16 Megabytes el total de la petición
        Interfaz.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
        
        
       
        #sincronizar_operadores()
        
       #Interfaz.run(host="0.0.0.0", port=5000, debug=True, ssl_context=None)
        Interfaz.run(host="0.0.0.0", port=5000, ssl_context='adhoc', debug=False)
