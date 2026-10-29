from flask import Flask, render_template, request, jsonify, url_for, redirect, session, g, flash, abort
import os
import secrets
import threading
import time
from config import connect, configuracion_activa, BaseDatosNoDisponible
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
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from logger import logger, contexto_peticion
from attachment_security import apply_attachment_headers
from schema_migrations import SchemaValidationError, validate_required_schema
from werkzeug.middleware.proxy_fix import ProxyFix
from backend_security import cargar_permisos, normalizar_uf_sesion, limiter
from autorizacion import regla_para

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

Interfaz = Flask(
    __name__,
    template_folder=str(BASE_DIR / "frontend"),
    static_folder=str(BASE_DIR / "Static")
)

# nginx termina el HTTPS y reenvía por el socket de Gunicorn; ProxyFix toma de sus
# cabeceras X-Forwarded-* (un solo proxy) el esquema https y la IP real del cliente.
Interfaz.wsgi_app = ProxyFix(Interfaz.wsgi_app, x_for=1, x_proto=1)

csrf = CSRFProtect()
csrf.init_app(Interfaz)
limiter.init_app(Interfaz)


@Interfaz.errorhandler(429)
def demasiados_intentos(e):
    logger.warning("login_bloqueado_por_intentos %s",
                   contexto_peticion(request.form.get("username") or "-"))
    flash('Demasiados intentos. Espere un minuto e inténtelo nuevamente.', 'error')
    return render_template('Front_login.html'), 429

# Sesión, cookies y límites según el entorno (APP_ENV: dev, qa o prod) en config.py.
Interfaz.config.from_object(configuracion_activa())
if not Interfaz.config.get("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY debe configurarse en el .env")

# Cada proceso de Gunicorn es independiente. Validar en su primera petición (y
# reintentar mientras SQL Server no responda); nunca al importar el módulo ni
# aplicando migraciones automáticamente.
_SCHEMA_VALIDATION_PID = None
_SCHEMA_VALIDATION_ERROR = None
_SCHEMA_VALIDATION_LOCK = threading.Lock()
# Último fallo transitorio: (pid, momento en que terminó el intento, mensaje).
_SCHEMA_FALLO_TRANSITORIO = None


def _validar_esquema_una_vez_por_proceso():
    global _SCHEMA_VALIDATION_PID, _SCHEMA_VALIDATION_ERROR
    process_id = os.getpid()
    if _SCHEMA_VALIDATION_PID == process_id:
        return _SCHEMA_VALIDATION_ERROR

    llegada = time.monotonic()
    with _SCHEMA_VALIDATION_LOCK:
        if _SCHEMA_VALIDATION_PID == process_id:
            return _SCHEMA_VALIDATION_ERROR
        # Los hilos que esperaban mientras otro intentaba conectar usan ese mismo
        # resultado en vez de repetir la espera uno tras otro; las peticiones que
        # llegan después del fallo sí reintentan.
        fallo = _SCHEMA_FALLO_TRANSITORIO
        if fallo and fallo[0] == process_id and fallo[1] >= llegada:
            return fallo[2]

        conn = None
        error = None
        try:
            conn = connect()
        except Exception as exc:
            # Fallo transitorio (SQL Server aún no responde, corte de red): no se
            # guarda en caché y se reintenta en la siguiente petición.
            logger.error("validacion_esquema_sqlserver_sin_conexion causa=%s", exc.__cause__ or exc)
            return _registrar_fallo_transitorio(
                process_id, "No fue posible conectar con SQL Server para validar el esquema requerido.")
        try:
            validate_required_schema(conn)
        except SchemaValidationError as exc:
            error = str(exc)
            logger.error("validacion_esquema_sqlserver_incompatible: %s", error)
        except Exception:
            # También puede ser transitorio (conexión cortada a mitad): se reintenta.
            logger.error("validacion_esquema_sqlserver_fallo_inesperado")
            return _registrar_fallo_transitorio(
                process_id,
                "No fue posible inspeccionar el esquema de SQL Server. Revise la conectividad y permisos de metadatos.")
        finally:
            conn.close()

        # Solo se guarda en caché el éxito o un esquema incompatible, que no se
        # corrige solo: tras aplicar las migraciones, reinicie Gunicorn.
        _SCHEMA_VALIDATION_PID = process_id
        _SCHEMA_VALIDATION_ERROR = error
        return error


def _registrar_fallo_transitorio(process_id, mensaje):
    global _SCHEMA_FALLO_TRANSITORIO
    _SCHEMA_FALLO_TRANSITORIO = (process_id, time.monotonic(), mensaje)
    return mensaje


def servicio_no_disponible():
    # El detalle (tablas, columnas, conexión) queda en app.log; al cliente, que
    # puede no tener sesión, solo se le da un mensaje genérico.
    return "Servicio no disponible temporalmente. Inténtelo más tarde.", 503


@Interfaz.before_request
def validar_esquema_antes_de_atender():
    error = _validar_esquema_una_vez_por_proceso()
    if error:
        return servicio_no_disponible()


@Interfaz.errorhandler(BaseDatosNoDisponible)
def base_de_datos_no_disponible(e):
    # Cualquier vista que no logre conectar responde 503 rápido (DB_CONNECT_TIMEOUT).
    # La causa (p. ej. certificado no válido o tiempo agotado) solo va al log.
    logger.error("sqlserver_no_disponible endpoint=%s causa=%s", request.endpoint, e.__cause__)
    return servicio_no_disponible()


CDN_LEAFLET = "https://unpkg.com/leaflet@1.9.4/dist/"
CDN_SCRIPTS = (
    CDN_LEAFLET,
    "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/",
    "https://cdn.jsdelivr.net/npm/leaflet.heat@0.2.0/dist/",
)


@Interfaz.context_processor
def incluir_nonce_csp():
    if not getattr(g, "csp_nonce", None):
        g.csp_nonce = secrets.token_urlsafe(18)
    return {"csp_nonce": g.csp_nonce}


@Interfaz.after_request
def agregar_csp(response):
    nonce = getattr(g, "csp_nonce", None) or secrets.token_urlsafe(18)
    if request.endpoint == "Modulo_unificado.descargar_archivo":
        return apply_attachment_headers(response)

    # Política única para todas las páginas: sin JavaScript en línea salvo con
    # nonce, sin manejadores on*= y solo las librerías externas con versión fija
    # (cada <script> externo lleva además su hash SRI en la plantilla).
    politica = (
        "default-src 'self'; base-uri 'self'; object-src 'none'; "
        "frame-ancestors 'self'; form-action 'self'; "
        f"script-src 'self' 'nonce-{nonce}' {' '.join(CDN_SCRIPTS)}; "
        "script-src-attr 'none'; "
        f"style-src 'self' 'unsafe-inline' {CDN_LEAFLET}; "
        f"img-src 'self' data: blob: {CDN_LEAFLET} https://*.tile.openstreetmap.org; "
        "connect-src 'self' https://nominatim.openstreetmap.org; "
        "font-src 'self' data:; media-src 'self' blob:"
    )

    response.headers["Content-Security-Policy"] = politica
    return response

@Interfaz.before_request
def proteger_rutas():
    # Regla de la ruta en el mapa central (autorizacion.py): estáticos y
    # pantallas de acceso son públicos; todo lo demás exige sesión y permiso.
    regla = regla_para(request.endpoint)
    if regla is not None and regla.publica:
        return

    # Todo lo demás requiere sesión
    if 'usuario' not in session:
        return redirect(url_for('Modulo_login.login'))

    # El cierre de sesión siempre está permitido.
    if request.endpoint == 'Modulo_login.logout':
        return

    # En cada petición se lee el estado actual del usuario, para que desactivarlo
    # o cambiarle permisos o UF aplique también a las sesiones ya abiertas.
    conn = None
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Activo, UF, ISNULL(Cambio_password_obligatorio, 0) FROM Table_usuarios WHERE Username = ?",
            session.get('usuario_id')
        )
        estado_usuario = cursor.fetchone()
        permisos = cargar_permisos(session.get('usuario_id'), cursor) if estado_usuario else []
    except BaseDatosNoDisponible:
        raise
    except Exception:
        logger.exception("error_verificar_estado_usuario %s", contexto_peticion())
        return servicio_no_disponible()
    finally:
        if conn:
            conn.close()

    # Usuario eliminado o desactivado: se cierra la sesión.
    if not estado_usuario or not estado_usuario[0]:
        logger.warning("sesion_revocada_usuario_inactivo %s", contexto_peticion())
        session.clear()
        flash('Su sesión fue cerrada porque el usuario se encuentra inactivo.', 'error')
        return redirect(url_for('Modulo_login.login'))

    _, uf, cambio_password_obligatorio = estado_usuario
    session['UF'] = normalizar_uf_sesion(uf)
    session['permisos'] = permisos

    # Autorización por defecto (MVC-8), con los permisos recién leídos: una ruta
    # sin regla en el mapa central se niega aunque su vista no tenga decorador.
    if request.endpoint is not None:
        if regla is None:
            logger.warning("ruta_sin_regla_de_autorizacion endpoint=%s %s",
                           request.endpoint, contexto_peticion())
            abort(403)
        if not regla.permite(permisos, request.view_args):
            abort(403)

    # La ruta de cambio sigue permitida aunque haya una obligación pendiente.
    # Profile.index consulta el estado para notificar a la interfaz de usuario
    # y permite mostrar la pantalla de cambio.
    if request.endpoint == 'Profile.cambiar_password':
        return

    if cambio_password_obligatorio:
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

# Pantalla de inicio: la primera del menú lateral que el usuario tiene permitida.
PANTALLAS_INICIO = (
    ('Ingresar_dashboard', 'Front_dashboard.index', {}),
    ('Ingresar_historico_danos', 'Historico_danos.index', {}),
    ('Ingresar_modulo__oper', 'Modulo_unificado.index', {'modulo': 'Operaciones'}),
    ('Ingresar_captur_danos', 'Capturador.index', {}),
    ('Ingresar_modulo__mtto', 'Modulo_unificado.index', {'modulo': 'Mtto'}),
    ('Ingresar_captur_reparaciones', 'Capturador_rep.index', {}),
    ('Ingresar_danos_vs_reparaciones', 'Historico_movil.index', {}),
    ('Ingresar_modulo__svial', 'Modulo_unificado.index', {'modulo': 'Svial'}),
    ('Ingresar_modulo__laboral', 'Modulo_unificado.index', {'modulo': 'laboral'}),
    ('Ingresar_crear_usuario', 'Modulo_usuario.crear_usuario', {}),
    ('Ingresar_asignar_permisos', 'Modulo_permisos_roles.asignar_permisos', {}),
)


@Interfaz.route('/interfaz')
def index():
    """Lleva a la primera pantalla permitida; sin ninguna, al perfil (siempre accesible)."""
    permisos = session.get('permisos', [])
    for permiso, endpoint, valores in PANTALLAS_INICIO:
        if permiso in permisos:
            return redirect(url_for(endpoint, **valores))
    return redirect(url_for('Profile.index'))


def es_peticion_ajax():
    """Peticiones fetch/AJAX: reciben JSON en vez de una página."""
    return (
        request.headers.get('Sec-Fetch-Dest') == 'empty'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.is_json
        or request.accept_mimetypes.best == 'application/json'
    )


MENSAJES_ERROR = {
    403: 'No tiene permiso para acceder a este recurso.',
    404: 'El recurso solicitado no existe.',
}


@Interfaz.errorhandler(404)
@Interfaz.errorhandler(403)
def error_acceso(e):
    # Sin sesión, al login. Con sesión se responde el código real, sin redirigir:
    # redirigir a /interfaz producía bucles y llegaba a las llamadas AJAX como HTML.
    if 'usuario' not in session:
        return redirect(url_for('Modulo_login.login'))
    mensaje = MENSAJES_ERROR[e.code]
    if es_peticion_ajax():
        return jsonify({'status': 'error', 'message': mensaje}), e.code
    return render_template('Front_error.html', codigo=e.code, mensaje=mensaje), e.code



if __name__ == "__main__":
        
       
        #sincronizar_operadores()
        
       #Interfaz.run(host="0.0.0.0", port=5000, debug=True, ssl_context=None)
        Interfaz.run(host="0.0.0.0", port=5000, ssl_context='adhoc', debug=False)
