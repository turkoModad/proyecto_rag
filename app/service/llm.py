import asyncio
from vllm import SamplingParams
from app.core.variables_locales import state
from app.core.config import MAX_NEW_TOKENS, TEMPERATURE, SYSTEM_PROMPT
import logging


logger = logging.getLogger("LLMService")


async def generate(question_text, context_text):
    try:
        prompt = f"""
        {SYSTEM_PROMPT}

        CONTEXTO:
        {context_text}

        PREGUNTA:
        {question_text}

        Respuesta:
        """
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