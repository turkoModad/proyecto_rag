import json
import logging
import numpy as np

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from qdrant_client.http.exceptions import UnexpectedResponse
from app.core.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_API_KEY,
    COLLECTION_LEY,
    COLLECTION_QA,
    DATASET_FILE,
    EMB_DIM,
    QA_SEARCH_THRESHOLD
)

from app.service.embedding import get_embedding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QdrantService")

# ------------------------
# QDRANT CLIENT
# ------------------------
try:
    client = QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY,
        https=False,
        timeout=60
    )
except Exception as e:
    logger.error(f"Error fatal al inicializar el cliente Qdrant: {e}")


# ------------------------
# COLLECTION HELPERS
# ------------------------
def ensure_qa_collection():
    """
    Verifica la existencia de la colección de Caché de Respuestas (QA).
    Si no existe, la crea configurando la dimensión de los vectores y 
    utilizando Distancia Coseno para la comparación semántica.
    """
    try:
        collections = client.get_collections().collections
        names = [c.name for c in collections]

        if COLLECTION_QA not in names:
            client.create_collection(
                collection_name=COLLECTION_QA,
                vectors_config=VectorParams(size=EMB_DIM, distance=Distance.COSINE)
            )
            logger.info(f"Colección '{COLLECTION_QA}' creada exitosamente.")
        else:
            logger.debug(f"La colección '{COLLECTION_QA}' ya existe.")
    except Exception as e:
        logger.error(f"Error al asegurar la colección QA: {e}")


def collection_is_empty(collection_name=COLLECTION_LEY):
    """Comprueba si hay datos en una colección. Retorna True si hay error o está vacía."""
    try:
        count_result = client.count(collection_name=collection_name, exact=True)
        return count_result.count == 0
    except UnexpectedResponse as e:
        logger.warning(f"La colección '{collection_name}' no parece existir: {e}")
        return True
    except Exception as e:
        logger.error(f"Error consultando conteo en {collection_name}: {e}")
        return True


# ------------------------
# LOAD DATASET
# ------------------------
def load_dataset_to_qdrant(batch_size=100):
    """
    Lee el archivo de leyes (.jsonl), genera embeddings para cada artículo y los sube a Qdrant.
    
    Proceso:
    1. Itera el dataset línea por línea para ahorrar memoria.
    2. Normaliza los vectores (L2 norm) para asegurar que la similitud coseno sea precisa.
    3. Carga los datos en batches (lotes) para optimizar el rendimiento de la red y la base de datos.
    """
    logger.info(f"Iniciando carga de dataset desde {DATASET_FILE}")
    points = []

    try:
        with open(DATASET_FILE, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                try:
                    obj = json.loads(line)
                    vector = get_embedding(obj["contenido"])
                    
                    # Evitar división por cero si el vector es nulo
                    norm = np.linalg.norm(vector)
                    vector = vector / norm if norm > 0 else vector

                    points.append({
                        "id": idx,
                        "vector": vector.tolist(),
                        "payload": obj
                    })

                    if len(points) >= batch_size:
                        client.upsert(collection_name=COLLECTION_LEY, points=points)
                        points = []
                        logger.info(f"Batch de {idx} registros cargado...")
                
                except json.JSONDecodeError:
                    logger.error(f"Error de formato JSON en línea {idx}. Saltando...")
                except Exception as line_err:
                    logger.error(f"Error procesando registro {idx}: {line_err}")

            if points:
                client.upsert(collection_name=COLLECTION_LEY, points=points)
        logger.info("Dataset cargado completamente.")
    except FileNotFoundError:
        logger.error(f"Archivo de dataset no encontrado en: {DATASET_FILE}")
    except Exception as e:
        logger.error(f"Error crítico durante la ingesta a Qdrant: {e}")



# ------------------------
# SEARCH LEY
# ------------------------
def search_ley(query_vector, top_k):
    """
    Realiza una búsqueda semántica en la colección de leyes.
    Retorna los 'top_k' fragmentos de texto (payloads) más similares al vector de consulta.
    """
    result = client.query_points(
        collection_name=COLLECTION_LEY,
        query=query_vector.tolist(),
        limit=top_k
    )
    return result.points


# ------------------------
# SEARCH QA CACHE
# ------------------------
def search_qa_cache(query_emb: np.ndarray, top_k=1):
    """
    Busca en la base de datos de preguntas ya respondidas para evitar llamadas redundantes al LLM.
    
    Lógica de decisión:
    - Si el score de similitud es mayor o igual al QA_SEARCH_THRESHOLD, se considera un 'hit'.
    - Si no hay resultados o el score es bajo, retorna None para proceder con el RAG normal.
    """
    try:
        result = client.query_points(
            collection_name=COLLECTION_QA,
            query=query_emb.tolist(),
            limit=top_k
        )

        if not result.points:
            return None, 0.0

        best = result.points[0]
        if best.score >= QA_SEARCH_THRESHOLD:
            return best.payload, best.score
        return None, best.score
    except Exception as e:
        logger.error(f"Error consultando caché QA: {e}")
        return None, 0.0


# ------------------------
# DUPLICATE DETECTOR
# ------------------------
def is_duplicate_qa(embedding: np.ndarray, threshold: float):
    """
    Verifica si una pregunta ya existe en la caché antes de intentar guardarla.
    Ayuda a mantener la colección de caché limpia y sin redundancias.
    """
    try:
        result = client.query_points(
            collection_name=COLLECTION_QA,
            query=embedding.tolist(),
            limit=1
        )
        if not result.points:
            return False
        return result.points[0].score >= threshold
    except Exception as e:
        logger.error(f"Error detectando duplicados: {e}")
        return False