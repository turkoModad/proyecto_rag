import smtplib
import socket
import logging
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import SMTP_PASSWORD, SMTP_SERVER, SMTP_USER, SMTP_PORT, SENDER_EMAIL, BASE_URL
from .otp_generator import generar_otp
from app.core.security import hash_email


logger = logging.getLogger("email_service")
logger.setLevel(logging.INFO)


if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _mask_email(email: str) -> str:
    """Muestra solo los primeros 5 caracteres antes del @ y enmascara el resto"""
    local, domain = email.split("@")
    visible = local[:5]
    masked = visible + "*" * max(len(local) - 5, 0)
    return f"{masked}@****.com"


def enviar_email(receiver_email: str, subject: str, body_html: str) -> bool:
    """Envía un email mostrando solo el correo parcialmente enmascarado en logs"""
    mensaje = MIMEMultipart()
    mensaje["From"] = SENDER_EMAIL
    mensaje["To"] = receiver_email
    mensaje["Subject"] = subject
    mensaje.attach(MIMEText(body_html, "html"))

    try:
        masked_email = _mask_email(receiver_email)
        logger.info(f"Iniciando envío de email a {masked_email}")

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, mensaje.as_string())
        server.quit()

        logger.info(f"Email enviado correctamente a {masked_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Credenciales SMTP incorrectas.")
    except socket.timeout:
        logger.error("Tiempo de espera agotado. Revisa el puerto SMTP.")
    except Exception as e:
        logger.exception(f"Error inesperado enviando email: {e}")

    return False


def generar_token_verificacion() -> str:
    """Genera un token seguro URL-safe para verificación"""
    return secrets.token_urlsafe(32)


def enviar_otp(receiver_email: str) -> dict:
    """
    Genera OTP y token de verificación, envía email seguro.
    Devuelve diccionario con otp y token (para guardar en DB)
    """
    otp = generar_otp()
    token = generar_token_verificacion()
    email_hash = hash_email(receiver_email)  

    verify_link = f"{BASE_URL}/auth/verify?token={token}"

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

            <p style="margin-top:20px;">Este código expirará en 10 minutos.</p>
            <p style="color:red;">No compartas este código con nadie.</p>
        </body>
    </html>
    """

    masked_email = _mask_email(receiver_email)
    enviado = enviar_email(receiver_email, "Código OTP de Verificación", html_body)
    if enviado:
        logger.info(f"OTP y token enviados exitosamente a {masked_email}")
        return {"otp": otp, "token": token, "email_hash": email_hash}
    else:
        logger.warning(f"No se pudo enviar OTP a {masked_email}")
        return None