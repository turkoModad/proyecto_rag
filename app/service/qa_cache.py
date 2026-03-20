import logging
import time
from sklearn.metrics.pairwise import cosine_similarity
from app.service.embedding import get_embedding
from app.db.vector_operations import search_qa_cache
from app.auth.service import count_user_queries, count_anonymous_queries, log_query
from app.core.config import SIM_CTX, TEMPERATURE, LIMITE_CON_AUTH, LIMITE_SIN_AUTH
from app.engine.auto_cache import append_qa_cache, should_autocache
import asyncio
from fastapi import HTTPException

logger = logging.getLogger("QACacheService")


# ----------------------------
# LÍMITES DE CONSULTAS (MODIFICADO)
# ----------------------------
async def check_anonymous_limit(db, ip_address: str):
    """
    Verifica límite para usuarios anónimos
    Retorna dict con información del límite en lugar de lanzar excepción
    """
    count = await count_anonymous_queries(db, ip_address, "/ask")
    logger.info(f"Anon query #{count+1} from {ip_address}")
    
    is_limited = count >= LIMITE_SIN_AUTH
    
    return {
        "count": count,
        "limit": LIMITE_SIN_AUTH,
        "is_limited": is_limited,
        "remaining": max(LIMITE_SIN_AUTH - count, 0)
    }


async def check_user_limit(db, current_user: dict):
    """
    Verifica límite para usuarios autenticados
    Retorna dict con información del límite
    """
    # Usuarios admin o premium no tienen límite
    if current_user["role"] != "free":
        return {
            "count": 0,
            "limit": None,  # Sin límite
            "is_limited": False,
            "remaining": None  # Ilimitado
        }
    
    count = await count_user_queries(db, current_user["sub"])
    logger.info(f"User {current_user['sub']} queries: {count}")
    
    is_limited = count >= LIMITE_CON_AUTH
    
    return {
        "count": count,
        "limit": LIMITE_CON_AUTH,
        "is_limited": is_limited,
        "remaining": max(LIMITE_CON_AUTH - count, 0)
    }


# ----------------------------
# CACHÉ DE PREGUNTAS (SIN CAMBIOS)
# ----------------------------
async def try_cache(query_text, current_user, db, ip_address, user_agent, start_time):
    try:
        q_emb = get_embedding(query_text, prefix="query")
        qa_hit, qa_score = search_qa_cache(q_emb)

        if qa_hit:
            logger.info("========== QA CACHE VALIDATION ==========")
            logger.info(f"[QA DEBUG] QA_SCORE={qa_score:.4f}")
            logger.info(f"[QA DEBUG] SIM_THRESHOLD={SIM_CTX:.4f}")
            logger.info(f"[QA DEBUG] Pregunta: {query_text}")
            logger.info(f"[QA DEBUG] Respuesta cache: {qa_hit.get('respuesta')}")
            logger.info("==========================================")

            if qa_score >= SIM_CTX:
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)
                generated_text = qa_hit["respuesta"]
                tokens_generated = len(generated_text.split())

                await log_query(
                    db=db,
                    user_id=current_user["sub"] if current_user else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    question=query_text,
                    response=generated_text,
                    decision="qa_cache",
                    tokens_generated=tokens_generated,
                    response_time_ms=response_time_ms,
                    endpoint="/ask",
                    model_used="cache",
                    qa_cache_score=qa_score,
                    grounding_score=qa_score
                )

                return {
                    "question": query_text,
                    "response": generated_text,
                    "decision": "qa_cache",
                    "qa_score": qa_score,
                    "ctx_validation": qa_score
                }

    except Exception as e:
        logger.warning(f"Fallo QA Cache: {e}")

    return None


# ----------------------------
# AUTO-CACHE DE RESPUESTAS (SIN CAMBIOS)
# ----------------------------
async def auto_cache(question, answer, context_text, top_scores):
    try:
        decision = should_autocache(top_scores, answer, context_text)

        if isinstance(decision, tuple):
            do_cache, grounding_score = decision
        else:
            do_cache = decision
            grounding_score = 0.0

        if not do_cache:
            return False, grounding_score

        retrieval_score = top_scores[0] if top_scores else 0.0

        success = await append_qa_cache(
            question=question,
            answer=answer,
            context_text=context_text,
            embedding=get_embedding(question),
            grounding_score=grounding_score,
            retrieval_score=retrieval_score
        )

        return success, grounding_score

    except Exception as e:
        logger.warning(f"No se pudo guardar en Auto-cache: {e}")
        return False, 0.0


# ----------------------------
# LOG FINAL DE PREGUNTAS (SIN CAMBIOS)
# ----------------------------
async def log_final(
    question,
    answer,
    current_user,
    db,
    ip_address,
    user_agent,
    start_time,
    top_scores: list[float] | None = None,
    was_autocached: bool = False,
    grounding_score: float = 0.0,
    decision: str | None = None
):
    end_time = time.time()
    response_time_ms = int((end_time - start_time) * 1000)
    tokens_generated = len(answer.split())

    if decision is None:
        if not answer:
            decision = "out_of_domain"
        else:
            decision = "rag_autocached" if was_autocached else "rag"

    if decision == "qa_cache":
        model_used = "cache"
    elif decision == "out_of_domain":
        model_used = "classifier"
    elif answer:  
        model_used = "llm"
    else:
        model_used = "none"

    await log_query(
        db=db,
        user_id=current_user["sub"] if current_user else None,
        ip_address=ip_address,
        user_agent=user_agent,
        question=question,
        response=answer or "",
        decision=decision,
        tokens_generated=tokens_generated,
        response_time_ms=response_time_ms,
        endpoint="/ask",
        model_used=model_used,
        temperature=TEMPERATURE if answer else None,
        top_k_retrieved=len(top_scores) if top_scores else None,
        qa_cache_score=max(top_scores) if top_scores else None,
        retrieval_score=max(top_scores) if top_scores else None,
        grounding_score=grounding_score
    )