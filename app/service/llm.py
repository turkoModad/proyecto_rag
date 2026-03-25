import asyncio
from vllm import SamplingParams
from app.core.variables_locales import state
from app.core.config import MAX_NEW_TOKENS, TEMPERATURE, SYSTEM_PROMPT
import logging


logger = logging.getLogger("LLMService")


# =========================================================
# GENERATE (RESPUESTA FINAL)
# =========================================================
async def generate(question_text: str, context_text: str):
    try:
        prompt = f"""{SYSTEM_PROMPT}

Antes de responder:

1. Determiná si la pregunta del usuario depende del contexto anterior.
2. Si depende, interpretala como una pregunta completa usando el contexto.
3. Si no depende, usala tal como está.
4. NO muestres la interpretación.
5. Respondé únicamente usando el CONTEXTO BASE.

{context_text}

PREGUNTA DEL USUARIO:
{question_text}

RESPUESTA:"""
        future = asyncio.get_running_loop().create_future()

        await state.llm_queue.put({
            "prompt": prompt,
            "sampling_params": SamplingParams(
                max_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE
            ),
            "future": future
        })

        return await future

    except Exception as e:
        logger.error(f"Error en generación LLM: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Servicio de generación no disponible")


# =========================================================
# REWRITE QUERY (ANTES DEL RAG)
# =========================================================
async def rewrite_query(question_text: str, conversation_memory: str = None):
    try:
        prompt = f"""
Reescribí la pregunta del usuario como una consulta de búsqueda clara, corta y autosuficiente.

Usá el historial SOLO si la pregunta depende del contexto anterior.

La consulta debe estar en minúsculas, no tener signos de pregunta, ser directa (estilo búsqueda)

Si la pregunta ya es clara, devolvela sin cambios.

NO respondas la pregunta.
NO expliques nada.
SOLO devolvé la consulta final.

Historial:
{conversation_memory or "N/A"}

Pregunta:
{question_text}

Consulta:
"""

        future = asyncio.get_running_loop().create_future()

        await state.llm_queue.put({
            "prompt": prompt,
            "sampling_params": SamplingParams(
                max_tokens=32,
                temperature=0.0
            ),
            "future": future
        })

        rewritten = await future

        # -----------------------------
        # LIMPIEZA DE SALIDA
        # -----------------------------
        rewritten = rewritten.strip().lower()

        if "consulta:" in rewritten:
            rewritten = rewritten.split("consulta:")[-1].strip()

        # fallback si algo raro pasa
        if not rewritten or len(rewritten) < 3:
            return question_text

        return rewritten

    except Exception as e:
        logger.error(f"Error en reescritura: {e}")
        return question_text