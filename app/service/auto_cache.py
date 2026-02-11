import time
import uuid
import logging
import numpy as np
from typing import List, Optional
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
from app.db.qdrant.functions_qdrant import client, is_duplicate_qa


logger = logging.getLogger("AutoCacheService")


def is_answer_grounded(answer_text: str, context_text: str) -> bool:
    """
    Verifica si la respuesta generada está sustentada (grounded) en el contexto recuperado.
    Utiliza similitud coseno entre los embeddings de ambos textos.
    """
    if not answer_text or not context_text:
        return False

    try:
        emb_answer = get_embedding(answer_text)
        emb_context = get_embedding(context_text)

        # Calculamos similitud entre respuesta y contexto
        sim = float(cosine_similarity([emb_answer], [emb_context])[0][0])
        
        logger.info(f"[AUTO CACHE] Grounding sim={sim:.4f} (Min req: {MIN_GEN_CTX_SIM})")
        return sim >= MIN_GEN_CTX_SIM
    
    except Exception as e:
        logger.error(f"Error calculando grounding: {e}")
        return False
    

def should_autocache(top_scores: List[float], generated_text: str, context_text: str) -> bool:
    """
    Aplica un pipeline de filtros para decidir si una respuesta es lo suficientemente
    confiable como para ser guardada en la caché semántica.
    """
    try:
        if not generated_text or not top_scores:
            return False
        
        # 1. Filtro de Longitud
        text_len = len(generated_text.strip())
        if not (MIN_ANSWER_LENGTH <= text_len <= MAX_ANSWER_LENGTH):
            logger.debug(f"Auto-cache rechazado: Longitud inválida ({text_len})")
            return False

        # 2. Filtro que evita cachear respuestas evasivas
        blacklist = [
            "no hay información suficiente", "no se puede determinar",
            "no puedo afirmar", "no consta", "no está especificado"
        ]
        if any(phrase in generated_text.lower() for phrase in blacklist):
            logger.debug("Auto-cache rechazado: Respuesta evasiva detectada.")
            return False

        # 3. Filtro de Confianza del Retrieval (Scores de Qdrant)
        best_score = max(top_scores)
        if best_score < AUTO_CACHE_THRESHOLD:
            logger.debug(f"Auto-cache rechazado: Score insuficiente ({best_score:.4f})")
            return False

        # 4. Filtro de Ambigüedad (Gap entre los dos mejores resultados)
        if len(top_scores) > 1:
            gap = abs(top_scores[0] - top_scores[1])
            if gap < AUTO_CACHE_GAP:
                logger.debug(f"Auto-cache rechazado: Alta ambigüedad (Gap: {gap:.4f})")
                return False

        # 5. Filtro de Grounding (Consistencia semántica con el contexto)
        if not is_answer_grounded(generated_text, context_text):
            logger.debug("Auto-cache rechazado: La respuesta no coincide semánticamente con el contexto.")
            return False

        return True
    
    except Exception as e:
        logger.error(f"Error en lógica de decisión should_autocache: {e}")
        return False
    

async def append_qa_cache(question: str, answer: str, embedding: np.ndarray) -> bool:
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