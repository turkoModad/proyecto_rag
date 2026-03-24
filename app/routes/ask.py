from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, get_db
from app.service import qa_cache, domain_classifier, rag, llm
from app.auth.contexto import get_last_user_query, build_conversation_context

import logging
import time
import asyncio

logger = logging.getLogger("AskRouter")
router = APIRouter()


class Query(BaseModel):
    text: str | None = None
    question: str | None = None

    @model_validator(mode="after")
    def set_text_from_question(self):
        if self.text is None and self.question is None:
            raise ValueError('Debe proporcionar "text" o "question"')
        if self.text is None:
            self.text = self.question
        return self


def get_real_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("CF-Connecting-IP") or request.client.host or "unknown"


@router.post("/ask")
async def process_query(
    request: Request,
    query: Query,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    ip_address = get_real_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")

    consulta_usuario = query.text

    try:
        # =========================================================
        # 1. CONTROL DE USO
        # =========================================================
        if current_user is None:
            limit_info = await qa_cache.check_anonymous_limit(db, ip_address)
        else:
            limit_info = await qa_cache.check_user_limit(db, current_user)

        if limit_info["is_limited"]:
            logger.warning(f"[LIMIT] Excedido | user={current_user or ip_address}")

            await qa_cache.log_final(
                question=consulta_usuario,
                rewritten_query=None,
                answer="Límite de consultas alcanzado",
                current_user=current_user,
                db=db,
                ip_address=ip_address,
                user_agent=user_agent,
                start_time=start_time,
                decision="limit_exceeded"
            )

            return JSONResponse(
                status_code=429,
                content={
                    "question": consulta_usuario,
                    "response": f"Has alcanzado el límite de {limit_info['limit']} consultas.",
                    "decision": "limit_exceeded"
                }
            )

        # =========================================================
        # 2. CONTEXTO DE CONVERSACIÓN
        # =========================================================
        last_query = await get_last_user_query(
            db,
            user_id=current_user["sub"] if current_user else None,
            ip_address=ip_address if not current_user else None
        )

        conversation_context = build_conversation_context(last_query)

        # =========================================================
        # 3. REWRITER
        # =========================================================
        consulta_busqueda = await llm.rewrite_query(
            consulta_usuario,
            conversation_context
        )

        logger.info(
            "[REWRITER]\n"
            f"  original   : {consulta_usuario}\n"
            f"  rewritten  : {consulta_busqueda}"
        )

        # =========================================================
        # 4. CACHE (con rewritten)
        # =========================================================
        cached = await qa_cache.try_cache(
            consulta_usuario,
            consulta_busqueda,
            current_user,
            db,
            ip_address,
            user_agent,
            start_time
        )

        if cached:
            logger.info("[CACHE] HIT")
            return cached

        # =========================================================
        # 5. CLASIFICADOR
        # =========================================================
        in_domain = await domain_classifier.is_in_domain(
            consulta_busqueda,
            current_user,
            db,
            ip_address,
            user_agent,
            start_time
        )

        if not in_domain:
            logger.warning("[DOMAIN] OUT")

            await qa_cache.log_final(
                question=consulta_usuario,
                rewritten_query=consulta_busqueda,
                answer="Fuera de dominio",
                current_user=current_user,
                db=db,
                ip_address=ip_address,
                user_agent=user_agent,
                start_time=start_time,
                decision="out_of_domain"
            )

            return {
                "question": consulta_usuario,
                "response": "Solo respondo sobre la Ley de Tránsito (24.449).",
                "is_domain": False
            }

        logger.info("[DOMAIN] OK")

        # =========================================================
        # 6. RAG
        # =========================================================
        context_text, top_scores, metadata = await asyncio.to_thread(
            rag.retrieve_context,
            consulta_busqueda
        )


        logger.info(f"[METADATA] {metadata}")

        logger.info(
            "[RAG]\n"
            f"  original   : {consulta_usuario}\n"
            f"  rewritten  : {consulta_busqueda}\n"
            f"  scores     : {[round(s,4) for s in top_scores]}\n"
            f"  ctx_len    : {len(context_text)}"
        )

        # =========================================================
        # 7. CONTEXTO FINAL LLM (CORREGIDO)
        # =========================================================
        if conversation_context:
            contexto_final = (
                f"{conversation_context.strip()}\n\n"
                f"CONTEXTO BASE:\n{context_text.strip()}"
            )
        else:
            contexto_final = f"CONTEXTO BASE:\n{context_text.strip()}"

        # =========================================================
        # 8. GENERACIÓN
        # =========================================================
        generated_text = await asyncio.wait_for(
            llm.generate(consulta_usuario, contexto_final),
            timeout=60
        )

        # =========================================================
        # 9. AUTO CACHE (con rewritten)
        # =========================================================
        was_autocached, grounding_score = await qa_cache.auto_cache(
            consulta_usuario,
            consulta_busqueda,
            generated_text,
            context_text,
            top_scores
        )

        # =========================================================
        # 10. LOG FINAL
        # =========================================================
        await qa_cache.log_final(
            question=consulta_usuario,
            rewritten_query=consulta_busqueda,
            answer=generated_text or "",
            current_user=current_user,
            db=db,
            ip_address=ip_address,
            user_agent=user_agent,
            start_time=start_time,
            top_scores=top_scores,
            was_autocached=was_autocached,
            grounding_score=grounding_score
        )

        logger.info("[DONE] respuesta generada")

        return {
            "question": consulta_usuario,
            "response": generated_text,
            "metadata": metadata,
            "is_domain": True,
            "decision": "rag_autocached" if was_autocached else "rag"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")