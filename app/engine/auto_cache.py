import time
import uuid
import logging
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.service.embedding import get_embedding
from app.core.config import (
    AUTO_CACHE_THRESHOLD,
    AUTO_CACHE_GAP,
    COLLECTION_QA,
    MIN_ANSWER_LENGTH,
    MAX_ANSWER_LENGTH,
    AUTO_CACHE_DUPLICATE_THRESHOLD,
    MIN_GEN_CTX_SIM
)
from app.db.vector_client import client
from app.db.vector_operations import is_duplicate_qa


logger = logging.getLogger("AutoCacheService")


def get_grounding_score(answer_text: str, context_text: str) -> float:
    """
    Calcula grounding como la máxima similitud entre la respuesta
    y cada chunk individual del contexto.
    """

    if not answer_text or not context_text:
        return 0.0

    try:
        emb_answer = get_embedding(answer_text)

        chunks = [c.strip() for c in context_text.split("\n\n") if c.strip()]

        if not chunks:
            return 0.0

        max_sim = 0.0

        for chunk in chunks:
            emb_chunk = get_embedding(chunk)
            sim = float(cosine_similarity([emb_answer], [emb_chunk])[0][0])
            max_sim = max(max_sim, sim)

        return max_sim

    except Exception as e:
        logger.error(f"Error calculando grounding: {e}")
        return 0.0
    

def should_autocache(top_scores: list[float], generated_text: str, context_text: str) -> tuple[bool, float]:

    grounding_score = 0.0

    try:
        if not generated_text or not top_scores:
            return False, grounding_score

        text_len = len(generated_text.strip())

        ordered_scores = sorted(top_scores, reverse=True)
        best_score = ordered_scores[0]
        gap = None

        if len(ordered_scores) > 1:
            gap = ordered_scores[0] - ordered_scores[1]

        # 1. Longitud
        if not (MIN_ANSWER_LENGTH <= text_len <= MAX_ANSWER_LENGTH):
            return False, grounding_score

        # 2. Evasiva
        blacklist = [
            "no hay información suficiente",
            "no se puede determinar",
            "no puedo afirmar",
            "no consta",
            "no está especificado"
        ]

        if any(phrase in generated_text.lower() for phrase in blacklist):
            return False, grounding_score

        # 3. Retrieval
        if best_score < AUTO_CACHE_THRESHOLD:
            return False, grounding_score

        # 4. Gap
        if gap is not None and gap < AUTO_CACHE_GAP:
            return False, grounding_score

        # 5. Grounding
        grounding_score = get_grounding_score(generated_text, context_text)

        if grounding_score < MIN_GEN_CTX_SIM:
            return False, grounding_score

        return True, grounding_score

    except Exception as e:
        logger.error(f"Error en should_autocache: {e}")
        return False, grounding_score
        

async def append_qa_cache(
    question: str,
    answer: str,
    context_text: str,
    embedding: np.ndarray,
    grounding_score: float,
    retrieval_score: float
) -> bool:
    """
    Inserta una nueva entrada en la colección de caché de Qdrant.
    Incluye verificación explícita de duplicados y auditoría completa.
    """

    try:
        # Chequeo de duplicado
        is_dup = is_duplicate_qa(
            embedding,
            threshold=AUTO_CACHE_DUPLICATE_THRESHOLD
        )

        if is_dup:
            return False

        # Payload
        payload = {
            "pregunta": question,
            "respuesta": answer,
            "contexto": context_text[:600],
            "grounding_score": grounding_score,
            "retrieval_score": retrieval_score,
            "origen": "auto_rag",
            "timestamp": int(time.time())
        }

        # Inserción
        client.upsert(
            collection_name=COLLECTION_QA,
            points=[
                {
                    "id": str(uuid.uuid4()),
                    "vector": embedding.tolist(),
                    "payload": payload
                }
            ]
        )

        return True

    except Exception as e:
        logger.error(f"[AUTO CACHE] Error crítico al guardar: {e}")
        return False