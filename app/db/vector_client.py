import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from app.core.config import (
    VECTOR_HOST,
    VECTOR_PORT,
    VECTOR_API_KEY,
    COLLECTION_QA,
    EMB_DIM
)


logger = logging.getLogger("VectorClient")


# ------------------------
# CLIENT INITIALIZATION
# ------------------------
try:
    client = QdrantClient(
        host=VECTOR_HOST,
        port=VECTOR_PORT,
        api_key=VECTOR_API_KEY,
        https=False,
        timeout=60
    )
except Exception as e:
    logger.error(f"Error fatal al inicializar el cliente de base de datos vectorial: {e}")
    raise e


# ------------------------
# INFRASTRUCTURE HELPERS
# ------------------------
def ensure_qa_collection():
    """
    Verifica la existencia de la colección de Caché de Respuestas (QA).
    Si no existe, la crea configurando la dimensión y la métrica.
    """
    try:
        collections = client.get_collections().collections
        names = [c.name for c in collections]

        if COLLECTION_QA not in names:
            client.create_collection(
                collection_name=COLLECTION_QA,
                vectors_config=VectorParams(size=EMB_DIM, distance=Distance.COSINE)
            )
            logger.info(f"Contenedor '{COLLECTION_QA}' inicializado exitosamente.")
        else:
            logger.debug(f"El contenedor '{COLLECTION_QA}' ya existe.")
    except Exception as e:
        logger.error(f"Error al asegurar infraestructura QA: {e}")