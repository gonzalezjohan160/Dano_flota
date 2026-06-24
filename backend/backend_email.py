import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def enviar_correo(destinatarios, asunto, mensaje_html):

    remitente = "***REMOVED***"
    password = "***REMOVED***"

    msg = MIMEMultipart()

    msg["From"] = remitente
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = asunto

    msg.attach(MIMEText(mensaje_html, "html"))

    servidor = smtplib.SMTP("smtp.gmail.com", 587)
    servidor.starttls()

    servidor.login(remitente, password)

    servidor.sendmail(
        remitente,
        destinatarios,
        msg.as_string()
    )

    servidor.quit()