import os
import logging
import hashlib 
from cryptography.fernet import Fernet
from dotenv import load_dotenv


load_dotenv()
logger = logging.getLogger("Security")


def _get_var_id(var_name: str) -> str:
    """Crea un identificador corto y anónimo para la variable"""
    return f"var_{hashlib.md5(var_name.encode()).hexdigest()[:6]}"


def inicializar_cifrador():
    master_key = os.getenv("MY_APP_MASTER_KEY")
    if not master_key:
        logger.critical("Acceso denegado: Llave maestra no configurada.")
        raise EnvironmentError("Error de infraestructura de seguridad.")
    return Fernet(master_key.encode())


cipher = inicializar_cifrador()


def get_secret(var_name, default=None):
    """Obtiene y descifra una variable sin revelar su nombre en logs."""
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