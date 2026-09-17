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
from pathlib import Path
from sincronizar_operadores import sincronizar_operadores

BASE_DIR = Path(__file__).resolve().parent.parent

Interfaz = Flask(
    __name__,
    template_folder=str(BASE_DIR / "frontend"),
    static_folder=str(BASE_DIR / "Static")
)

Interfaz.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=20)
Interfaz.config["SESSION_REFRESH_EACH_REQUEST"] = True
Interfaz.config["SESSION_COOKIE_HTTPONLY"] = True
Interfaz.config["SESSION_COOKIE_SAMESITE"] = "Lax"

Interfaz.secret_key = "***REMOVED***"

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
        print(Interfaz.url_map)
        
       
        #sincronizar_operadores()
        
       #Interfaz.run(host="0.0.0.0", port=5000, debug=True, ssl_context=None)
        Interfaz.run(host="0.0.0.0", port=5000, ssl_context='adhoc', debug=True)
