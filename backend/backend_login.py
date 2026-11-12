from repositories.sesiones import sesion_bd
from contextlib import closing

from flask import Blueprint, request, session, redirect, flash, render_template, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import secrets
import datetime
import os
from config import connect
from backend_security import (
    cargar_permisos,
    normalizar_uf_sesion,
    validar_politica_password,
    hash_token_restablecimiento,
    limiter,
    usuario_del_formulario,
    LIMITE_INTENTOS_LOGIN,
    LIMITE_INTENTOS_IP,
)
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import BASE_DIR
from logger import logger, contexto_peticion
from modelos import autenticacion as modelo_autenticacion

def enviar_email(destinatario, link):
    remitente = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if not remitente or not password:
        raise RuntimeError("Configuración SMTP incompleta")

    mensaje = MIMEMultipart()
    mensaje["From"] = remitente
    mensaje["To"] = destinatario
    mensaje["Subject"] = "Restablecer contraseña - GDAMAGES DANO A FLOTA"

    cuerpo = f"""
Buen día,

Se solicitó un restablecimiento de contraseña para tu cuenta.

Haz clic en el siguiente enlace para crear una nueva contraseña:

{link}

Este enlace expirará en 30 minutos.

Si no solicitaste este cambio, puedes ignorar este mensaje.

GDAMAGES GMASIVO SOLUTIONS
"""

    mensaje.attach(MIMEText(cuerpo, "plain"))

    with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"),
                       int(os.getenv("SMTP_PORT", "587")), timeout=20) as servidor:
        servidor.starttls()
        servidor.login(remitente, password)
        servidor.send_message(mensaje)

def construir_enlace_restablecimiento(token):
    """Arma el enlace con APP_BASE_URL y nunca con la cabecera Host de la petición.

    Si el enlace dependiera del Host, un atacante podría pedir la recuperación
    de otra cuenta con un Host propio y recibir el token en su dominio.
    """
    base_url = (os.getenv("APP_BASE_URL") or "").strip().rstrip("/")
    if not base_url.startswith("https://"):
        raise RuntimeError("APP_BASE_URL debe configurarse con la URL https pública del aplicativo")
    return base_url + url_for('Modulo_login.reset_password', token=token)


Modulo_login = Blueprint(
    'Modulo_login',
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)




def _login_fallido(response):
    # Un login exitoso redirige; solo los intentos fallidos consumen el límite.
    return response.status_code != 302


@Modulo_login.route('/', methods=['GET', 'POST'])
@limiter.limit(LIMITE_INTENTOS_IP, methods=['POST'], deduct_when=_login_fallido)
@limiter.limit(LIMITE_INTENTOS_LOGIN, methods=['POST'], deduct_when=_login_fallido,
               key_func=usuario_del_formulario)
def login():
    # Si ya inició sesión, no mostrar nuevamente el login
    if 'usuario' in session:
        return redirect('/interfaz')

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            # closing() cierra cursor y conexión siempre, también si la consulta falla.
            with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
                usuario = modelo_autenticacion.buscar_usuario_para_login(cursor, username)
        except Exception:
            logger.exception("error_bd_login %s", contexto_peticion(username))
            flash('No fue posible procesar el inicio de sesión. Inténtelo nuevamente.', 'error')
            return render_template('Front_login.html')


        if usuario:
            user_id, password_hash, uf, activo, cambio_password_obligatorio, nombre_usuario = usuario
            if check_password_hash(password_hash, password):
                if not activo:
                    logger.warning("login_usuario_inactivo %s", contexto_peticion(username))
                    flash('El usuario se encuentra inactivo. No tiene permitido ingresar al aplicativo.', 'error')
                    return render_template('Front_login.html')

                session['usuario'] = nombre_usuario
                session['usuario_id'] = user_id
                session.permanent = True
                session['UF'] = normalizar_uf_sesion(uf)
                session['permisos'] = cargar_permisos(user_id)
                logger.info("login_exitoso %s", contexto_peticion(username))
                if cambio_password_obligatorio:
                    return redirect(url_for('Profile.index'))
                return redirect('/interfaz')

        logger.warning("login_fallido %s", contexto_peticion(username))
        flash('Usuario o contraseña incorrectos', 'error')

    return render_template('Front_login.html')


@Modulo_login.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit(LIMITE_INTENTOS_IP, methods=['POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        try:
            # closing() cierra cursor y conexión siempre; el rollback se hace antes,
            # todavía con la conexión abierta, y el error sigue al except de abajo.
            with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
                try:
                    usuario = modelo_autenticacion.buscar_id_por_correo(cursor, email)
                    ahora = datetime.datetime.now()

                    if usuario:
                        # Un enlace nuevo anula los anteriores del mismo usuario.
                        modelo_autenticacion.anular_enlaces_pendientes(cursor, usuario[0])

                    # Purga (BD-8): los tokens vencidos, usados o anulados ya no sirven y
                    # no se conservan. Se hace en cada solicitud, exista o no el correo.
                    modelo_autenticacion.purgar_enlaces_sin_uso(cursor, ahora)

                    token = None
                    if usuario:
                        token = secrets.token_urlsafe(32)
                        modelo_autenticacion.guardar_enlace(
                            cursor, usuario[0], hash_token_restablecimiento(token),
                            ahora + datetime.timedelta(minutes=30))
                    conn.commit()

                    if token:
                        reset_link = construir_enlace_restablecimiento(token)
                        enviar_email(email, reset_link)
                except Exception:
                    conn.rollback()
                    raise
        except Exception:
            logger.exception("error_solicitud_restauracion_contrasena %s", contexto_peticion("-"))

        flash("Si el correo existe, se enviaron instrucciones.", "info")
        return redirect(url_for('Modulo_login.login'))

    return render_template('Front_olvido_contrasena.html')


@Modulo_login.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        # closing() cierra cursor y conexión siempre; el rollback se hace antes,
        # todavía con la conexión abierta, y el error sigue al except de abajo.
        with sesion_bd(connect) as conn, closing(conn.cursor()) as cursor:
            try:
                token_hash = hash_token_restablecimiento(token)
                registro = modelo_autenticacion.buscar_enlace(cursor, token_hash)

                if not registro:
                    return "Token inválido", 400

                user_id, expiration, used, username = registro
                if used:
                    return "Token ya utilizado", 400
                if datetime.datetime.now() > expiration:
                    return "Token expirado", 400

                if request.method == 'POST':
                    nueva_password = request.form.get('password')
                    error = validar_politica_password(nueva_password, username)
                    if error:
                        return render_template('Front_resetear_contrasena.html', error=error), 400

                    # Reclama el token dentro de la transacción para impedir su uso concurrente.
                    if modelo_autenticacion.reclamar_enlace(cursor, token_hash, datetime.datetime.now()) != 1:
                        conn.rollback()
                        return "Token inválido, expirado o ya utilizado", 400

                    hash_nuevo = generate_password_hash(nueva_password)
                    if modelo_autenticacion.cambiar_contrasena(cursor, hash_nuevo, user_id) != 1:
                        conn.rollback()
                        return "No fue posible actualizar la contraseña", 500

                    conn.commit()
                    logger.info("restablecimiento_contrasena_exitoso %s", contexto_peticion(username))
                    flash("Contraseña actualizada correctamente", "success")
                    return redirect(url_for('Modulo_login.login'))

                return render_template('Front_resetear_contrasena.html')
            except Exception:
                conn.rollback()
                raise
    except Exception:
        logger.exception("error_restauracion_contrasena %s", contexto_peticion("-"))
        return "No fue posible procesar la solicitud. Inténtelo nuevamente.", 500

@Modulo_login.route('/logout', methods=['POST'])
def logout():
    logger.info("logout %s", contexto_peticion())
    session.clear() # Limpia todos los datos
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('Modulo_login.login'))

@Modulo_login.after_app_request # <--- Nota el "app_request"
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    # Cabeceras de seguridad en todas las respuestas. setdefault conserva las
    # más estrictas que ya traen los adjuntos (/archivo usa X-Frame-Options DENY).
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    return response



