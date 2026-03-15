import logging
import numpy as np
from fastapi import HTTPException

from app.db.vector_operations import search_ley
from app.service.embedding import get_embedding
from app.service.reranker import rerank
from app.core.config import TOP_K, SECURITY, RERANK_TOP_K


logger = logging.getLogger("RAGService")


def retrieve_context(question_text: str):
    """
    Pipeline completo de Retrieval:
    1) Genera embedding de la pregunta
    2) Busca en Qdrant
    3) Aplica rerank si es necesario
    4) Construye contexto final
    """
    try:
        # 1- VALIDACIÓN  
        if not isinstance(question_text, str) or not question_text.strip():
            logger.warning("Pregunta vacía en retrieve_context.")
            return "", []


        # 2- GENERAR EMBEDDING
        query_embedding = get_embedding(question_text, prefix="query")

        if isinstance(query_embedding, list):
            query_embedding = np.array(query_embedding)

        if not isinstance(query_embedding, np.ndarray):
            logger.error(f"Embedding inválido: {type(query_embedding)}")
            raise HTTPException(status_code=500, detail="Error interno de embedding")

        # Normalización si tus vectores fueron normalizados al indexar
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm


        # 3- BÚSQUEDA VECTORIAL
        results = search_ley(query_embedding, TOP_K)

        if not results:
            logger.info("Sin resultados en búsqueda vectorial.")
            return "", []


        # 4- RERANK CONDICIONAL
        if len(results) > 1 and results[0].score < SECURITY:
            logger.info("Aplicando rerank por score bajo.")
            results = rerank(question_text, results)

        # Limitar resultados finales
        results = results[:RERANK_TOP_K]


        # 5- CONSTRUIR CONTEXTO
        context_parts = []
        top_scores = []

        for hit in results:
            payload = hit.payload or {}

            titulo = payload.get("titulo", "")
            articulo = payload.get("numero_articulo", "")
            contenido = payload.get("contenido", "")

            if not contenido:
                continue

            # formatted = f"{titulo} Art. {articulo} - {contenido}".strip()
            formatted = contenido.strip()
            context_parts.append(formatted)
            top_scores.append(hit.score)

        if not context_parts:
            logger.info("Resultados encontrados pero sin contenido útil.")
            return "", []

        context_text = "\n\n".join(context_parts)

        logger.info(
            f"Retrieval OK | chunks={len(context_parts)} | "
            f"max_score={max(top_scores):.4f}"
        )

        return context_text, top_scores

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error crítico en Retrieval (Qdrant): {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error al recuperar contexto legal"
        )