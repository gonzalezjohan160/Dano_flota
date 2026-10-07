from flask import Blueprint, request, session, redirect, flash, render_template, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import secrets
import datetime
import os
from config import connect
from backend_security import cargar_permisos
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import BASE_DIR
from logger import logger

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

Modulo_login = Blueprint(
    'Modulo_login',
    __name__,
    template_folder=str(BASE_DIR/"frontend"),
    static_folder=str(BASE_DIR/"Static")
)




@Modulo_login.route('/', methods=['GET', 'POST'])
def login():
    # Si ya inició sesión, no mostrar nuevamente el login
    if 'usuario' in session:
        return redirect('/interfaz')
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = None
        try:
            conn = connect()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Username, PasswordHash, UF, Activo,
                       ISNULL(Cambio_password_obligatorio, 0)
                FROM Table_usuarios
                WHERE Username = ?
            """, username)
            usuario = cursor.fetchone()
            
        except Exception:
            logger.exception("error_bd_login")
            flash('No fue posible procesar el inicio de sesión. Inténtelo nuevamente.', 'error')
            return render_template('Front_login.html')    
        finally:
            if conn:
                conn.close()
        

        if usuario:
            user_id, password_hash, uf, activo, cambio_password_obligatorio = usuario
            if check_password_hash(password_hash, password):
                if not activo:
                    logger.warning("login_usuario_inactivo")
                    flash('El usuario se encuentra inactivo. No tiene permitido ingresar al aplicativo.', 'error')
                    return render_template('Front_login.html')
                
                session['usuario'] = username
                session['usuario_id'] = user_id
                session.permanent = True
                session['UF'] = str(uf).strip() if uf else "0"
                session['permisos'] = cargar_permisos(user_id)
                logger.info("login_exitoso")
                if cambio_password_obligatorio:
                    return redirect(url_for('Profile.index'))
                return redirect('/interfaz')
            
        logger.warning("login_fallido")
        flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('Front_login.html')


@Modulo_login.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        conn = None
        try:
            conn = connect()
            cursor = conn.cursor()
            cursor.execute("SELECT ConsID FROM Table_usuarios WHERE Email = ?", email)
            usuario = cursor.fetchone()

            if usuario:
                user_id = usuario[0]
                token = secrets.token_urlsafe(32)
                expiration = datetime.datetime.now() + datetime.timedelta(minutes=30)
                cursor.execute("""
                    INSERT INTO Table_password_reset (UserId, Token, Expiration)
                    VALUES (?, ?, ?)
                """, (user_id, token, expiration))
                conn.commit()

                reset_link = url_for('Modulo_login.reset_password', token=token, _external=True)
                enviar_email(email, reset_link)
        except Exception:
            if conn:
                conn.rollback()
            logger.exception("error_solicitud_restauracion_contrasena")
        finally:
            if conn:
                conn.close()

        flash("Si el correo existe, se enviaron instrucciones.", "info")
        return redirect(url_for('Modulo_login.login'))

    return render_template('Front_olvido_contrasena.html')


@Modulo_login.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    conn = None
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT UserId, Expiration, Used
            FROM Table_password_reset
            WHERE Token = ?
        """, token)
        registro = cursor.fetchone()

        if not registro:
            return "Token inválido", 400

        user_id, expiration, used = registro
        if used:
            return "Token ya utilizado", 400
        if datetime.datetime.now() > expiration:
            return "Token expirado", 400

        if request.method == 'POST':
            nueva_password = request.form.get('password')
            if not nueva_password:
                return "La contraseña es obligatoria", 400

            # Reclama el token dentro de la transacción para impedir su uso concurrente.
            cursor.execute("""
                UPDATE Table_password_reset
                SET Used = 1
                WHERE Token = ? AND Used = 0 AND Expiration >= ?
            """, (token, datetime.datetime.now()))
            if cursor.rowcount != 1:
                conn.rollback()
                return "Token inválido, expirado o ya utilizado", 400

            hash_nuevo = generate_password_hash(nueva_password)
            cursor.execute("""
                UPDATE Table_usuarios
                SET PasswordHash = ?
                WHERE ConsID = ?
            """, (hash_nuevo, user_id))
            if cursor.rowcount != 1:
                conn.rollback()
                return "No fue posible actualizar la contraseña", 500

            conn.commit()
            flash("Contraseña actualizada correctamente", "success")
            return redirect(url_for('Modulo_login.login'))

        return render_template('Front_resetear_contrasena.html')
    except Exception:
        if conn:
            conn.rollback()
        logger.exception("error_restauracion_contrasena")
        return "No fue posible procesar la solicitud. Inténtelo nuevamente.", 500
    finally:
        if conn:
            conn.close()

@Modulo_login.route('/logout', methods=['POST'])
def logout():
    session.clear() # Limpia todos los datos
    flash('Has cerrado sesión correctamente', 'info')
    return redirect(url_for('Modulo_login.login'))

@Modulo_login.after_app_request # <--- Nota el "app_request"
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response



