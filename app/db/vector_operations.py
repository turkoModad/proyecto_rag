import json
import logging
import numpy as np
from qdrant_client.http.exceptions import UnexpectedResponse
from app.db.vector_client import client
from app.core.config import (
    COLLECTION_LEY,
    COLLECTION_QA,
    DATASET_FILE,
    QA_SEARCH_THRESHOLD
)
from app.service.embedding import get_embedding


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VectorOperations")


def collection_is_empty(collection_name=COLLECTION_LEY):
    """Comprueba si hay datos en una colección. Retorna True si está vacía."""
    try:
        count_result = client.count(collection_name=collection_name, exact=True)
        return count_result.count == 0
    except UnexpectedResponse as e:
        logger.warning(f"La colección '{collection_name}' no parece existir: {e}")
        return True
    except Exception as e:
        logger.error(f"Error consultando estado en {collection_name}: {e}")
        return True


def load_dataset_to_qdrant(batch_size=100):
    """Lee el dataset local, genera embeddings y los sube a la base vectorial."""
    logger.info(f"Iniciando carga de datos desde fuente: {DATASET_FILE}")
    points = []

    try:
        with open(DATASET_FILE, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                try:
                    obj = json.loads(line)
                    vector = get_embedding(obj["contenido"], prefix="passage")
                    
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
                        logger.info(f"Batch de {idx + 1} registros procesado...")
                
                except json.JSONDecodeError:
                    logger.error(f"Error de formato en línea {idx}. Saltando...")
                except Exception as line_err:
                    logger.error(f"Error procesando registro {idx}: {line_err}")

            if points:
                client.upsert(collection_name=COLLECTION_LEY, points=points)
        logger.info("Carga de datos finalizada correctamente.")

    except FileNotFoundError:
        logger.error(f"Archivo de origen no encontrado: {DATASET_FILE}")
    except Exception as e:
        logger.error(f"Error crítico durante la ingesta: {e}")


def search_ley(query_vector, top_k):
    """Realiza una búsqueda semántica en la colección principal."""
    try:
        result = client.query_points(
            collection_name=COLLECTION_LEY,
            query=query_vector.tolist(),
            limit=top_k
        )
        return result.points
    
    except Exception as e:
        logger.error(f"Error en búsqueda de base de conocimientos: {e}")
        return []

def search_qa_cache(query_emb: np.ndarray, top_k=1):
    """Busca en la caché semántica de respuestas previas."""
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
        logger.error(f"Error consultando caché semántica: {e}")
        return None, 0.0


def is_duplicate_qa(embedding: np.ndarray, threshold: float):
    """Verifica si una entrada similar ya existe para evitar redundancia."""
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