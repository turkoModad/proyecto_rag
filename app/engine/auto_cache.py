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
    Verifica si la respuesta generada está sustentada (grounded) en el contexto recuperado.
    Utiliza similitud coseno entre los embeddings de ambos textos.
    """
    if not answer_text or not context_text:
        return 0.0

    try:
        emb_answer = get_embedding(answer_text)
        emb_context = get_embedding(context_text)

        # Calculamos similitud entre respuesta y contexto
        sim = float(cosine_similarity([emb_answer], [emb_context])[0][0])        
        logger.info(f"[AUTO CACHE] Grounding sim={sim:.4f} (Min req: {MIN_GEN_CTX_SIM})")
        return sim
    
    except Exception as e:
        logger.error(f"Error calculando grounding: {e}")
        return 0.0
    

def should_autocache(top_scores: list[float], generated_text: str, context_text: str) -> tuple[bool, float]:
    """
    Pipeline de filtros para decidir si una respuesta debe guardarse en la caché.
    Devuelve siempre (bool, grounding_score).
    """
    grounding_score = 0.0
    try:
        if not generated_text or not top_scores:
            return False, grounding_score
        
        # 1. Filtro de Longitud
        text_len = len(generated_text.strip())
        if not (MIN_ANSWER_LENGTH <= text_len <= MAX_ANSWER_LENGTH):
            logger.debug(f"Auto-cache rechazado: Longitud inválida ({text_len})")
            return False, grounding_score

        # 2. Filtro de respuestas evasivas
        blacklist = [
            "no hay información suficiente", "no se puede determinar",
            "no puedo afirmar", "no consta", "no está especificado"
        ]
        if any(phrase in generated_text.lower() for phrase in blacklist):
            logger.debug("Auto-cache rechazado: Respuesta evasiva detectada.")
            return False, grounding_score

        # 3. Filtro de confianza del Retrieval
        best_score = max(top_scores)
        if best_score < AUTO_CACHE_THRESHOLD:
            logger.debug(f"Auto-cache rechazado: Score insuficiente ({best_score:.4f})")
            return False, grounding_score

        # 4. Filtro de Ambigüedad (Gap entre los dos mejores resultados)
        if len(top_scores) > 1:
            gap = abs(top_scores[0] - top_scores[1])
            if gap < AUTO_CACHE_GAP:
                logger.debug(f"Auto-cache rechazado: Alta ambigüedad (Gap: {gap:.4f})")
                return False, grounding_score

        # 5. Filtro de Grounding (similitud semántica con el contexto)
        grounding_score = get_grounding_score(generated_text, context_text)
        if grounding_score < MIN_GEN_CTX_SIM:
            logger.debug(f"Auto-cache rechazado: Grounding insuficiente ({grounding_score:.4f})")
            return False, grounding_score

        # Si pasa todos los filtros
        return True, grounding_score

    except Exception as e:
        logger.error(f"Error en lógica de decisión should_autocache: {e}")
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
    Incluye una verificación final de duplicados antes de la inserción.
    """
    try:
        if is_duplicate_qa(embedding, threshold=AUTO_CACHE_DUPLICATE_THRESHOLD):
            logger.info("[AUTO CACHE] Descartado: Ya existe una pregunta similar en caché.")
            return False

        payload = {
            "pregunta": question,
            "respuesta": answer,
            "contexto": context_text[:800],
            "grounding_score": grounding_score,
            "retrieval_score": retrieval_score,
            "origen": "auto_rag",
            "timestamp": int(time.time())
        }


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

        logger.info(f"[AUTO CACHE] Guardado exitoso: {question[:50]}...")
        return True

    except Exception as e:
        logger.error(f"Error crítico al guardar en QA Cache: {e}")
        return False