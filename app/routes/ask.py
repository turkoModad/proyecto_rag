from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, get_db
from app.service import qa_cache, domain_classifier, rag, llm
import logging
import time
import asyncio
from app.core.config import LIMITE_CON_AUTH, LIMITE_SIN_AUTH


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

    try:
        # -----------------------------
        # CONTROL DE USO (MODIFICADO)
        # -----------------------------
        if current_user is None:
            limit_info = await qa_cache.check_anonymous_limit(db, ip_address)
        else:
            limit_info = await qa_cache.check_user_limit(db, current_user)
        
        # Verificar si excedió el límite
        if limit_info["is_limited"]:
            logger.warning(f"Límite excedido para IP {ip_address if not current_user else current_user['sub']}")
            
            # Loggear el intento fallido (pero no contar como consulta válida)
            await qa_cache.log_final(
                question=query.text,
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
                    "question": query.text,
                    "response": f"Has alcanzado el límite de {limit_info['limit']} consultas.",
                    "decision": "limit_exceeded",
                    "queries_used": limit_info["count"],
                    "queries_limit": limit_info["limit"],
                    "remaining": 0
                }
            )

        # -----------------------------
        # CACHE PREVIO
        # -----------------------------
        cached = await qa_cache.try_cache(
            query.text, current_user, db, ip_address, user_agent, start_time
        )
        
        if cached:
            try:
                logger.info(f"RESPUESTA CACHE: {cached.get('response')}")
            except Exception:
                logger.info("No se pudo leer respuesta cache")
            
            # Agregar info de límites a la respuesta cache
            cached["queries_used"] = limit_info["count"] + 1
            cached["queries_limit"] = limit_info["limit"]
            cached["remaining"] = limit_info["remaining"] - 1 if limit_info["remaining"] is not None else None

        # -----------------------------
        # CLASIFICADOR DE DOMINIO
        # -----------------------------
        in_domain = await domain_classifier.is_in_domain(
            query.text, current_user, db, ip_address, user_agent, start_time
        )

        # -----------------------------
        # RESPUESTA PARA PREGUNTAS FUERA DE DOMINIO
        # -----------------------------
        if not in_domain:
            await qa_cache.log_final(
                question=query.text,
                answer="Lo siento, solo puedo responder preguntas relacionadas con la Ley de Tránsito (24.449) y sus normas complementarias. Tu consulta parece tratar sobre otro tema. Si crees que me equivoqué, por favor intenta redactar tu pregunta de nuevo dándome más detalles sobre la situación vial que te interesa.",
                current_user=current_user,
                db=db,
                ip_address=ip_address,
                user_agent=user_agent,
                start_time=start_time,
                top_scores=None,
                was_autocached=False,
                grounding_score=0.0,
                decision="out_of_domain"
            )

            return {
                "question": query.text,
                "response": "Lo siento, solo puedo responder preguntas relacionadas con la Ley de Tránsito (24.449) y sus normas complementarias. Tu consulta parece tratar sobre otro tema. Si crees que me equivoqué, por favor intenta redactar tu pregunta de nuevo dándome más detalles sobre la situación vial que te interesa.",
                "is_domain": False,
                "decision": "out_of_domain",
                "queries_used": limit_info["count"] + 1,
                "queries_limit": limit_info["limit"],
                "remaining": limit_info["remaining"] - 1 if limit_info["remaining"] is not None else None
            }

        # -----------------------------
        # RAG
        # -----------------------------
        context_text, top_scores = await asyncio.to_thread(
            rag.retrieve_context,
            query.text
        )

        # -----------------------------
        # DEBUG CONTEXTO RECUPERADO
        # -----------------------------
        logger.info("========== RAG CONTEXT DEBUG ==========")
        logger.info(f"SCORES: {top_scores}")
        logger.info(f"Tamaño contexto LLM: {len(context_text)} caracteres")
        if context_text:
            logger.info("CONTEXTO RECUPERADO:")
            for i, chunk in enumerate(context_text.split("\n\n"), 1):
                logger.info(f"[CTX {i}] {chunk[:200]}...") 
        else:
            logger.info("CONTEXTO VACÍO")

        # -----------------------------
        # LLM
        # -----------------------------
        try:
            generated_text = await asyncio.wait_for(
                llm.generate(query.text, context_text),
                timeout=60
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="El modelo tardó demasiado en responder"
            )

        # -----------------------------
        # AUTO CACHE
        # -----------------------------
        was_autocached, grounding_score = await qa_cache.auto_cache(
            query.text,
            generated_text,
            context_text,
            top_scores
        )

        # -----------------------------
        # LOG FINAL CON RESPUESTA REAL
        # -----------------------------
        try:
            await qa_cache.log_final(
                question=query.text,
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
        except Exception as log_error:
            logger.warning(f"No se pudo loguear la respuesta generada: {log_error}")
        
        # -----------------------------
        # RETORNAR RESPUESTA FINAL
        # -----------------------------
        return {
            "question": query.text,
            "response": generated_text,
            "is_domain": True,
            "decision": "rag_autocached" if was_autocached else "rag",
            "queries_used": limit_info["count"] + 1,
            "queries_limit": limit_info["limit"],
            "remaining": limit_info["remaining"] - 1 if limit_info["remaining"] is not None else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error no controlado en /ask: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")