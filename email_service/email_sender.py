import smtplib
import socket
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import (
    SMTP_PASSWORD,
    SMTP_SERVER,
    SMTP_USER,
    SMTP_PORT,
    SENDER_EMAIL
)

from .otp_generator import generar_otp


BASE_URL = "https://seguridadvial.codepyhub.com"
# --------------------------------------------------
# LOGGER CONFIG
# --------------------------------------------------

logger = logging.getLogger("email_service")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# --------------------------------------------------
# EMAIL SENDER
# --------------------------------------------------

def enviar_email(receiver_email: str, subject: str, body_html: str) -> bool:

    mensaje = MIMEMultipart()
    mensaje["From"] = SENDER_EMAIL
    mensaje["To"] = receiver_email
    mensaje["Subject"] = subject
    mensaje.attach(MIMEText(body_html, "html"))

    try:
        logger.info(f"Iniciando envío de email a {receiver_email}")

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, mensaje.as_string())
        server.quit()

        logger.info(f"Email enviado correctamente a {receiver_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Credenciales SMTP incorrectas.")
    except socket.timeout:
        logger.error("Tiempo de espera agotado. Revisa el puerto SMTP.")
    except Exception as e:
        logger.exception(f"Error inesperado enviando email a {receiver_email}: {e}")

    return False


# --------------------------------------------------
# OTP SENDER
# --------------------------------------------------

def enviar_otp(receiver_email: str) -> str:

    otp = generar_otp()

    verify_link = f"{BASE_URL}/auth/verify?email={receiver_email}"

    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>Verificación de Cuenta</h2>

            <p>Tu código de verificación es:</p>

            <h1 style="letter-spacing: 5px;">{otp}</h1>

            <p>O puedes verificar tu cuenta haciendo clic en el siguiente enlace:</p>

            <a href="{verify_link}" 
               style="display:inline-block;
                      padding:10px 20px;
                      background-color:#1a73e8;
                      color:white;
                      text-decoration:none;
                      border-radius:5px;">
                Verificar Cuenta
            </a>

            <p style="margin-top:20px;">
                Este código expirará en 10 minutos.
            </p>

            <p style="color:red;">
                No compartas este código con nadie.
            </p>
        </body>
    </html>
    """

    logger.info(f"Generando OTP para {receiver_email}")

    if enviar_email(receiver_email, "Código OTP de Verificación", html_body):
        logger.info(f"OTP enviado exitosamente a {receiver_email}")
        return otp
    else:
        logger.warning(f"No se pudo enviar OTP a {receiver_email}")
        return None