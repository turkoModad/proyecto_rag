import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import socket
from app.core.config import SMTP_PASSWORD, SMTP_SERVER, SMTP_USER, SMTP_PORT, SENDER_EMAIL 


def enviar_email(receiver_email: str, subject: str, body_html: str) -> bool:
    mensaje = MIMEMultipart()
    mensaje["From"] = SENDER_EMAIL
    mensaje["To"] = receiver_email
    mensaje["Subject"] = subject
    mensaje.attach(MIMEText(body_html, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, mensaje.as_string())
        server.quit()
        return True
    except smtplib.SMTPAuthenticationError:
        print("Error: Credenciales SMTP incorrectas.")
    except socket.timeout:
        print("Error: Tiempo de espera agotado. Revisa el puerto 587.")
    except Exception as e:
        print(f"Error inesperado: {e}")
    return False


def enviar_otp(receiver_email: str) -> str:
    from .otp_generator import generar_otp

    otp = generar_otp()
    html_body = f"""
    <html>
        <body>
            <h2>Verificación de Cuenta</h2>
            <p>Tu código de verificación es: <b>{otp}</b></p>
            <p>No compartas este código con nadie.</p>
        </body>
    </html>
    """
    if enviar_email(receiver_email, "Código OTP de Verificación", html_body):
        print(f"OTP enviado a {receiver_email}")
    else:
        print(f"No se pudo enviar el OTP a {receiver_email}")
        otp = None
    return otp