import logging
import time
from sklearn.metrics.pairwise import cosine_similarity
from app.service.embedding import get_embedding
from app.db.vector_operations import search_qa_cache
from app.auth.service import count_user_queries, count_anonymous_queries, log_query
from app.core.config import SIM_CTX, TEMPERATURE
from app.engine.auto_cache import append_qa_cache, should_autocache
import asyncio
from fastapi import HTTPException


logger = logging.getLogger("QACacheService")


async def check_anonymous_limit(db, ip_address: str):
    count = await count_anonymous_queries(db, ip_address, "/ask")
    logger.info(f"Anon query #{count+1} from {ip_address}")
    if count >= 5:        
        raise HTTPException(status_code=401, detail="Límite de 5 consultas anónimo alcanzado.")


async def check_user_limit(db, current_user: dict):
    if current_user["role"] == "free":
        count = await count_user_queries(db, current_user["sub"])
        logger.info(f"User {current_user['sub']} queries: {count}")
        if count >= 20:            
            raise HTTPException(status_code=403, detail="Límite de 20 consultas alcanzado para usuarios FREE.")
        

async def try_cache(query_text, current_user, db, ip_address, user_agent, start_time):
    try:
        q_emb = get_embedding(query_text)
        qa_hit, qa_score = search_qa_cache(q_emb)
        if qa_hit:
            contexto_cache = qa_hit.get("contexto")
            sim_ctx = 0
            if contexto_cache:
                emb_context_cache = get_embedding(contexto_cache)
                sim_ctx = float(cosine_similarity([q_emb],[emb_context_cache])[0][0])
                logger.info(f"Validación cache sim_ctx={sim_ctx:.4f}")
            if sim_ctx >= SIM_CTX:
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
                    grounding_score=sim_ctx
                )
                return {
                    "question": query_text,
                    "response": generated_text,
                    "decision": "qa_cache",
                    "qa_score": qa_score,
                    "ctx_validation": sim_ctx
                }
    except Exception as e:
        logger.warning(f"Fallo QA Cache: {e}")
    return None


async def auto_cache(question, answer, context_text, top_scores):
    try:
        
        grounding_score = 0.0
        decision = should_autocache(top_scores, answer, context_text)
        if isinstance(decision, tuple):
            do_cache, grounding_score = decision
        else:
            do_cache = decision
        if do_cache:
            retrieval_score = top_scores[0] if top_scores else 0.0
            logger.info("Guardando respuesta en QA Cache...")            
            asyncio.create_task(
                append_qa_cache(
                    question=question,
                    answer=answer,
                    context_text=context_text,
                    embedding=get_embedding(question),
                    grounding_score=grounding_score,
                    retrieval_score=retrieval_score
                )
            )
    except Exception as e:
        logger.warning(f"No se pudo guardar en Auto-cache: {e}")


async def log_final(question, answer, current_user, db, ip_address, user_agent, start_time, top_scores):
    
    end_time = time.time()
    response_time_ms = int((end_time - start_time) * 1000)
    tokens_generated = len(answer.split())
    await log_query(
        db=db,
        user_id=current_user["sub"] if current_user else None,
        ip_address=ip_address,
        user_agent=user_agent,
        question=question,
        response=answer,
        decision="rag",
        tokens_generated=tokens_generated,
        response_time_ms=response_time_ms,
        endpoint="/ask",
        model_used="llm",
        temperature=TEMPERATURE,
        top_k_retrieved=len(top_scores),
        retrieval_score=top_scores[0] if top_scores else 0.0,
        grounding_score=0.0
    )