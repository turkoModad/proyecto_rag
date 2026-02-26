from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, get_db
from app.service import qa_cache, domain_classifier, rag, llm
import logging
import time


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


@router.post("/ask")
async def process_query(
    request: Request,
    query: Query,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    try:
        ip_address = (
            request.headers.get("CF-Connecting-IP")  
            or request.headers.get("x-forwarded-for")
            or request.client.host
        )
        user_agent = request.headers.get("user-agent")

        # --- CONTROL DE USO ---
        if current_user is None:
            await qa_cache.check_anonymous_limit(db, ip_address)
        else:
            await qa_cache.check_user_limit(db, current_user)

        # --- QA CACHE ---
        result = await qa_cache.try_cache(query.text, current_user, db, ip_address, user_agent, start_time)
        if result:
            return result

        # --- DOMINIO ---
        in_domain = await domain_classifier.is_in_domain(query.text, current_user, db, ip_address, user_agent, start_time)
        if in_domain is False:
            return {
                "question": query.text,
                "response": "La pregunta está fuera del dominio legal de tránsito.",
                "is_domain": False,
                "decision": "out_of_domain"
            }

        # --- RAG ---
        context_text, top_scores = rag.retrieve_context(query.text)

        # --- LLM ---
        generated_text = await llm.generate(query.text, context_text)

        # --- AUTO-CACHE ---
        await qa_cache.auto_cache(query.text, generated_text, context_text, top_scores)

        # --- LOG FINAL ---
        await qa_cache.log_final(query.text, generated_text, current_user, db, ip_address, user_agent, start_time, top_scores)

        return {
            "question": query.text,
            "response": generated_text,
            "is_domain": True,
            "decision": "rag"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error no controlado en /ask: {e}", exc_info=True)
        return {"error": "Internal Server Error", "detail": str(e)}