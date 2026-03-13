import os
import logging
import hashlib 
from cryptography.fernet import Fernet
from dotenv import load_dotenv


load_dotenv()
logger = logging.getLogger("Security")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def _get_var_id(var_name: str) -> str:
    """Crea un identificador corto y anónimo para la variable"""
    return f"var_{hashlib.md5(var_name.encode()).hexdigest()[:6]}"


def inicializar_cifrador():
    """Inicializa el cifrador con la master key del sistema"""
    master_key = os.getenv("MY_APP_MASTER_KEY")
    if not master_key:
        logger.critical("Acceso denegado: Llave maestra no configurada.")
        raise EnvironmentError("Error de infraestructura de seguridad.")
    return Fernet(master_key.encode())


cipher = inicializar_cifrador()


def get_secret(var_name, default=None):
    var_id = _get_var_id(var_name) 
    encrypted_value = os.getenv(var_name, default)
    if not encrypted_value:
        logger.error(f"Fallo de carga: Recurso {var_id} no disponible.")
        raise EnvironmentError(f"Error en configuración de secretos ({var_id}).")
    try:
        return cipher.decrypt(encrypted_value.encode()).decode()
    except Exception:
        logger.error(f"Error de integridad en recurso {var_id}.")
        raise ValueError(f"No se pudo validar el secreto {var_id}.")
    

def encrypt_value(value: str) -> str:
    """Cifra un valor de texto plano para almacenar en DB (no determinístico)."""
    if not value:
        raise ValueError("No se puede cifrar un valor vacío")
    return cipher.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str) -> str:
    """Descifra un valor previamente cifrado."""
    if not encrypted_value:
        raise ValueError("No se puede descifrar un valor vacío")
    try:
        return cipher.decrypt(encrypted_value.encode()).decode()
    except Exception:
        logger.error("Error al descifrar el valor")
        raise ValueError("No se pudo descifrar el valor correctamente")
    

def generate_var_id(value: str) -> str:
    """Genera un identificador seguro y anónimo para cualquier valor"""
    return f"id_{hashlib.md5(value.encode()).hexdigest()[:8]}"


# ----------------------------
# NUEVO: HASH DETERMINÍSTICO PARA EMAILS
# ----------------------------
def hash_email(email: str) -> str:
    """
    Genera un hash determinístico para emails.
    Útil para búsquedas y OTP.
    """
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()