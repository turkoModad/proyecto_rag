import os

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
import logging
from app.core.security import get_secret


logger = logging.getLogger("Config")


# ==========================================
# 1. SECRETS
# ==========================================
try:
    EMBEDDING = get_secret("EMBEDDING")
    MODELO_GENERADOR = get_secret("MODELO_GENERADOR")
    VECTOR_API_KEY = get_secret("VECTOR_API_KEY")
    CLASIFICADOR = get_secret("CLASIFICADOR")
    SERVER_URL = get_secret("SERVER_URL")    
    VECTOR_HOST = get_secret("VECTOR_HOST")       
    COLLECTION_LEY = get_secret("COLLECTION_LEY")
    COLLECTION_QA = get_secret("COLLECTION_QA")    
    DATASET_FILE = get_secret("DATASET_FILE")
    OUTPUT_JSONL = get_secret("OUTPUT_JSONL", "output.jsonl")
    RERANKER = get_secret("RERANKER")
    DB_USER= get_secret("DB_USER")
    DB_PASSWORD= get_secret("DB_PASSWORD")
    DB_NAME= get_secret("DB_NAME")
    DB_HOST= get_secret("DB_HOST")
    DB_PORT= int(get_secret("DB_PORT"))
    ADMIN_DATABASE_URL= get_secret("ADMIN_DATABASE_URL")
    USER_DATABASE_URL=  get_secret("USER_DATABASE_URL")
    JWT_SECRET= get_secret("JWT_SECRET")
    SMTP_SERVER = get_secret("SMTP_SERVER")
    SMTP_PORT = int(get_secret("SMTP_PORT", 587))
    SMTP_USER = get_secret("SMTP_USER")
    SMTP_PASSWORD = get_secret("SMTP_PASSWORD")
    SENDER_EMAIL = get_secret("SENDER_EMAIL")


except Exception as e:
    logger.critical("Fallo crítico: No se pudieron cargar los recursos base.")
    raise e

# ==========================================
# 2. INFRAESTRUCTURA Y HARDWARE
# ==========================================
VECTOR_PORT = 6333  
EMB_DIM = 1024

# ==========================================
# 3. LÓGICA DE RECUPERACIÓN (RETRIEVAL)
# ==========================================
TOP_K = 7
RERANK_TOP_K = 3
SECURITY = 0.86   

# ==========================================
# 4. LÓGICA DE CACHÉ Y CALIDAD
# ==========================================
QA_SEARCH_THRESHOLD = 0.87
QA_DUPLICATE_THRESHOLD = 0.91
AUTO_CACHE_THRESHOLD = 0.89
AUTO_CACHE_GAP = 0.01
AUTO_CACHE_DUPLICATE_THRESHOLD = 0.90
MIN_GEN_CTX_SIM = 0.88
MIN_ANSWER_LENGTH = 12
MAX_ANSWER_LENGTH = 800
SIM_CTX = 0.80

# ==========================================
# 5. PARÁMETROS DEL GENERADOR (LLM)
# ==========================================
LLM_BATCH_SIZE = 12
LLM_BATCH_TIMEOUT = 0.02
UTILIZACION_GPU = 0.65
MAX_MODEL_LENGTH = 1680
MAX_NEW_TOKENS = 220
TEMPERATURE = 0.05


try:
    if torch.cuda.is_available():
        DEVICE = torch.device("cuda:0")
    else:
        logger.warning("GPU no disponible, usando CPU (Rendimiento degradado)")
        DEVICE = torch.device("cpu")
except Exception as e:
    logger.error(f"Error al inicializar el dispositivo: {e}")
    DEVICE = torch.device("cpu")


# ==========================================
# 6. PROMPT DEL SISTEMA
# ==========================================
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