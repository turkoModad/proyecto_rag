import os

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import logging
from app.core.security import get_secret


logger = logging.getLogger("Config")


# 1. SECRETS
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
    RECIPIENT_EMAIL = get_secret("RECIPIENT_EMAIL")
    SECRET_EXAMENES = get_secret("SECRET_EXAMENES")
    ARCHIVO_PREGUNTAS = get_secret("ARCHIVO_PREGUNTAS")
    LLM_API_KEY = get_secret("LLM_API_KEY")


except Exception as e:
    logger.critical("Fallo crítico: No se pudieron cargar los recursos base.")
    raise e


# 2. INFRAESTRUCTURA Y HARDWARE
VECTOR_PORT = 443  
EMB_DIM = 1024
LIMITE_SIN_AUTH = 30
LIMITE_CON_AUTH = 60
MAX_OTP_PER_IP = 10
BASE_URL = "https://seguridadvial.codepyhub.com"


# 3. LÓGICA DE RECUPERACIÓN (RETRIEVAL)
TOP_K = 4
RERANK_TOP_K = 2
SECURITY = 0.86   


# 4. LÓGICA DE CACHÉ Y CALIDAD
QA_SEARCH_THRESHOLD = 0.90
QA_DUPLICATE_THRESHOLD = 0.90
AUTO_CACHE_THRESHOLD = 0.95
AUTO_CACHE_GAP = 0.005
AUTO_CACHE_DUPLICATE_THRESHOLD = 0.90
MIN_GEN_CTX_SIM = 0.82
MIN_ANSWER_LENGTH = 6
MAX_ANSWER_LENGTH = 800
SIM_CTX = 0.80


# 5. PARÁMETROS DEL GENERADOR (LLM)
LLM_BATCH_SIZE = 2
LLM_BATCH_TIMEOUT = 0.05
UTILIZACION_GPU = 0.65
MAX_MODEL_LENGTH = 10500       #3840
MAX_NEW_TOKENS = 1536           #1536
TEMPERATURE = 0.05

DEVICE = "cuda:0"


SYSTEM_PROMPT = (
    "Sos un asistente especializado en normas de tránsito argentinas.\n"
    "Respondé únicamente con la información explícita y más relevante del CONTEXTO BASE.\n"
    "NO agregues interpretaciones, conclusiones ni inferencias propias.\n"
    "Respondé de forma breve, clara y directa, como para un ciudadano común.\n"
    "Incluí siempre una breve razón o justificación basada en el contexto para evitar respuestas de una sola palabra.\n"
    "No menciones artículos, incisos ni lenguaje legal.\n"
    "Respondé de forma concisa en 1 a 4 oraciones: usá una sola si es suficiente, y solo ampliá hasta 4 si la pregunta lo requiere.\n"
    "No utilices negritas, asteriscos ni ningún tipo de formato de texto enriquecido (Markdown).\n"
    "Si se proporciona HISTORIAL RECIENTE, usalo únicamente para interpretar la intención de la pregunta actual. Nunca lo uses como fuente de información ni extraigas datos de allí.\n"
    "Por ejemplo, si el usuario pregunta '¿y en calles?' después de haber preguntado por velocidades en rutas,\n"
    "debés interpretar que se refiere a 'velocidad máxima en calles urbanas'.\n"
    "\n"
    "Si el contexto no alcanza para responder con certeza, respondé exactamente:\n"
    "\"No puedo responder con certeza con la información disponible. Por favor, reformule la pregunta usando términos claros y concretos sobre normas de tránsito.\""
)


# 7. SEGURIDAD Y RATE LIMITING
RATE_LIMIT_REQUESTS_PER_MINUTE = 60  # Máximo 60 requests por minuto por IP
RATE_LIMIT_WINDOW_MINUTES = 1        
BLOCK_DURATION_MINUTES = 15          
MAX_FAILED_ATTEMPTS = 10    
LIMITE_CARACTERES_MENSAJE = 600          

# horarios de limpieza db ip
CLEANUP_HOURS_LOCAL = [(0, 0)]

# Tiempo de retención de logs (en minutos)
LOG_RETENTION_MINUTES = 1440

VALID_ROLES = ["free", "admin"]

# duracion del token de la contraseña del admin
SESSION_PASSWORD_EXPIRE_MINUTES = 120