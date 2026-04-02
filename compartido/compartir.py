from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from vllm import SamplingParams
from app.core.variables_locales import state
from compartido.middleware_autenticacion import verify_llm_request
import asyncio
from typing import Optional
import logging


logger = logging.getLogger("LLM_API")


router = APIRouter(prefix="/llm", tags=["LLM API"], dependencies=[Depends(verify_llm_request)])


class PromptRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = Field(512, description="Máximo de tokens a generar")
    temperature: Optional[float] = Field(0.7, description="Creatividad (0.0 a 2.0)")
    top_p: Optional[float] = Field(0.95, description="Nucleus sampling")
    top_k: Optional[int] = Field(50, description="Top K sampling")
    repetition_penalty: Optional[float] = Field(1.0, description="Penalización por repetición")
    stop: Optional[list[str]] = Field(None, description="Tokens de parada")


class PromptResponse(BaseModel):
    response: str
    prompt: str
    max_tokens: int
    temperature: float


@router.post("/generate", response_model=PromptResponse)
async def generate(request: PromptRequest, req: Request):
    """
    LLM puro con seguridad: IP Whitelist (dinámica) + API Key
    """
    try:
        future = asyncio.get_running_loop().create_future()
        
        sampling_params = SamplingParams(
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
            repetition_penalty=request.repetition_penalty,
            stop=request.stop
        )
        
        await state.llm_queue.put({
            "prompt": request.prompt,
            "sampling_params": sampling_params,
            "future": future
        })
        
        respuesta = await asyncio.wait_for(future, timeout=60.0)
        
        return PromptResponse(
            response=respuesta,
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
    except Exception as e:
        logger.error(f"Error en LLM: {e}")
        raise HTTPException(status_code=503, detail=str(e))



@router.get("/health")
async def health():
    """Verificar que el LLM está disponible"""
    return {
        "status": "ok",
        "llm_loaded": state.llm is not None,
        "queue_size": state.llm_queue.qsize() if hasattr(state.llm_queue, 'qsize') else 0
    }