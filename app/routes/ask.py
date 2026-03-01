from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, get_db
from app.service import qa_cache, domain_classifier, rag, llm
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
    """
    Obtiene IP real considerando proxies como Cloudflare.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    return (
        request.headers.get("CF-Connecting-IP")
        or request.client.host
        or "unknown"
    )


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
        # CONTROL DE USO
        if current_user is None:
            await qa_cache.check_anonymous_limit(db, ip_address)
        else:
            await qa_cache.check_user_limit(db, current_user)

        # CACHE PREVIO
        cached = await qa_cache.try_cache(
            query.text, current_user, db,
            ip_address, user_agent, start_time
        )
        if cached:
            return cached

        # CLASIFICADOR DE DOMINIO
        in_domain = await domain_classifier.is_in_domain(
            query.text, current_user, db,
            ip_address, user_agent, start_time
        )

        if not in_domain:
            return {
                "question": query.text,
                "response": "La pregunta está fuera del dominio legal de tránsito.",
                "is_domain": False,
                "decision": "out_of_domain"
            }

        # RAG
        context_text, top_scores = await asyncio.to_thread(
            rag.retrieve_context,
            query.text
        )

        # LLM
        try:
            generated_text = await asyncio.wait_for(
                llm.generate(query.text, context_text),
                timeout=50
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail="El modelo tardó demasiado en responder"
            )

        # AUTO CACHE (capturamos resultado real)
        was_autocached, grounding_score = await qa_cache.auto_cache(
            query.text,
            generated_text,
            context_text,
            top_scores
        )

        # LOG FINAL
        await qa_cache.log_final(
            query.text,
            generated_text,
            current_user,
            db,
            ip_address,
            user_agent,
            start_time,
            top_scores,
            was_autocached=was_autocached,
            grounding_score=grounding_score
        )

        return {
            "question": query.text,
            "response": generated_text,
            "is_domain": True,
            "decision": "rag_autocached" if was_autocached else "rag"
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Error no controlado en /ask: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )