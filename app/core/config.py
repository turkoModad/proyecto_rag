import os

os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import torch
import logging
from dotenv import load_dotenv
from cryptography.fernet import Fernet


load_dotenv()

logger = logging.getLogger("Config")


def inicializar_cifrador():
    master_key = os.getenv("MY_APP_MASTER_KEY")
    if not master_key:
        logger.critical("No se encontró 'MY_APP_MASTER_KEY' en el sistema.")
        raise EnvironmentError("MY_APP_MASTER_KEY faltante.")
    return Fernet(master_key.encode())


cipher = inicializar_cifrador()


def get_secret(var_name, default=None):
    """Obtiene y descifra una variable del .env"""
    encrypted_value = os.getenv(var_name, default)
    if not encrypted_value:
        raise EnvironmentError(f"Variable cifrada {var_name} no encontrada en el .env")
    try:
        return cipher.decrypt(encrypted_value.encode()).decode()
    except Exception:
        logger.error(f"Error al descifrar {var_name}.")
        raise


def get_env_var(var_name, default=None, required=True):
    """Obtiene una variable de entorno normal y valida su existencia."""
    value = os.getenv(var_name, default)
    if required and value is None:
        logger.error(f"Falta la variable de entorno obligatoria: {var_name}")
        raise EnvironmentError(f"Variable {var_name} no encontrada en el .env")
    return value


try:
    EMBEDDING = get_secret("EMBEDDING")
    MODELO_GENERADOR = get_secret("MODELO_GENERADOR")
    QDRANT_API_KEY = get_secret("QDRANT_API_KEY")
    CLASIFICADOR = get_secret("CLASIFICADOR")
    SERVER_URL = get_secret("SERVER_URL")    
    QDRANT_HOST = get_secret("QDRANT_HOST")       
    COLLECTION_LEY = get_secret("COLLECTION_LEY")
    COLLECTION_QA = get_secret("COLLECTION_QA")    
    DATASET_FILE = get_secret("DATASET_FILE")
    OUTPUT_JSONL = get_secret("OUTPUT_JSONL", "output.jsonl")
    RERANKER = get_secret("RERANKER")

    QDRANT_PORT = int(get_env_var("QDRANT_PORT", 6333)) 

except Exception as e:
    logger.critical(f"Error cargando la configuración: {e}")
    raise


EMB_DIM = 1024
TOP_K = 6
RERANK_TOP_K = 2
SECURITY = 0.84

QA_SEARCH_THRESHOLD = 0.92
QA_DUPLICATE_THRESHOLD = 0.91
AUTO_CACHE_THRESHOLD = 0.87
AUTO_CACHE_GAP = 0.015
AUTO_CACHE_DUPLICATE_THRESHOLD = 0.90
MIN_GEN_CTX_SIM = 0.82
MIN_ANSWER_LENGTH = 12
MAX_ANSWER_LENGTH = 800

LLM_BATCH_SIZE = 12
LLM_BATCH_TIMEOUT = 0.02
UTILIZACION_GPU = 0.65
MAX_MODEL_LENGTH = 1680
MAX_NEW_TOKENS = 192
TEMPERATURE = 0.0


try:
    if torch.cuda.is_available():
        DEVICE = torch.device("cuda:0")
    else:
        logger.warning("GPU no disponible, usando CPU (Rendimiento degradado)")
        DEVICE = torch.device("cpu")
except Exception as e:
    logger.error(f"Error al inicializar el dispositivo: {e}")
    DEVICE = torch.device("cpu")


SYSTEM_PROMPT = (
    "Sos un asistente especializado en normas de tránsito argentinas.\n"
    "Respondé SOLO con la información del CONTEXTO.\n"
    "Respondé de forma breve, clara y directa, como para un ciudadano común.\n"
    "Contestá únicamente lo que se pregunta, sin agregar explicaciones innecesarias.\n"
    "No menciones artículos, incisos ni lenguaje legal.\n"
    "Usá como máximo 2-4 oraciones, salvo que la pregunta requiera una lista.\n"
    "Si el contexto no alcanza para responder con certeza, respondé exactamente:\n"
    "\"No hay información suficiente en el contexto para responder esta pregunta.\""
)