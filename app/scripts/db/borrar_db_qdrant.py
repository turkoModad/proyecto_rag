import os
import logging
import warnings
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.config import QDRANT_API_KEY, QDRANT_HOST, COLLECTION_QA, QDRANT_PORT, COLLECTION_LEY


warnings.filterwarnings("ignore", message=".*Api key is used with an insecure connection.*")

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("Maintenance")


QDRANT_URL = f"http://{QDRANT_HOST}:{QDRANT_PORT}"

def borrar_datos_coleccion():
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

        logger.info("Verificando integridad de las colecciones...")
        collections = client.get_collections().collections
        
        if not any(c.name == COLLECTION_QA for c in collections):
            logger.warning("La entidad objetivo no existe.")
            return

        logger.info("Ejecutando purga de registros...")
        client.delete(
            collection_name=COLLECTION_QA,
            points_selector=models.Filter() 
        )
        logger.info("Proceso finalizado exitosamente.")

    except Exception as e:
        logger.error("Error crítico durante la operación de mantenimiento.")

if __name__ == "__main__":
    borrar_datos_coleccion()