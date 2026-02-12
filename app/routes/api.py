import asyncio
import torch
import gc
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from vllm import SamplingParams
from contextlib import asynccontextmanager

from app.service.embedding import get_embedding
from app.service.auto_cache import should_autocache, append_qa_cache
from app.core.variables_locales import state
from app.core.config import (
    TOP_K, DEVICE, SYSTEM_PROMPT, MAX_NEW_TOKENS, 
    TEMPERATURE, SECURITY, RERANK_TOP_K
)
from app.core.models_loader import cargar_modelos
from app.engine.generator import llm_batch_worker
from app.db.qdrant.functions_qdrant import (
    ensure_qa_collection, collection_is_empty,
    search_ley, search_qa_cache, load_dataset_to_qdrant
)
from app.service.reranker import rerank


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("APIRoutes")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación: Carga de modelos y arranque del worker."""
    try:
        logger.info("Iniciando servicios RAG...")
        cargar_modelos()
        ensure_qa_collection()

        if collection_is_empty():
            logger.info("Base de datos vacía. Iniciando ingesta de dataset...")
            load_dataset_to_qdrant()

        app.state.worker_task = asyncio.create_task(llm_batch_worker())
        logger.info("Sistema RAG listo y Worker en ejecución.")
    except Exception as e:
        logger.error(f"Fallo crítico en el arranque: {e}")
        raise

    yield

    logger.info("Cerrando servicios...")
    app.state.worker_task.cancel()
    try:
        await app.state.worker_task
    except asyncio.CancelledError:
        logger.info("Worker detenido correctamente.")
    
    # Liberación de memoria
    state.clf_model = None
    state.llm = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logger.info("Memoria GPU liberada.")

app = FastAPI(lifespan=lifespan)

class Query(BaseModel):
    text: str

@app.post("/ask")
async def process_query(query: Query):
    """Endpoint principal para procesamiento de consultas RAG."""
    try:
        # 1. CLASIFICADOR
        try:
            inputs = state.clf_tokenizer(query.text, return_tensors="pt", truncation=True).to(DEVICE)
            with torch.no_grad():
                logits = state.clf_model(**inputs).logits
                probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
            
            is_in_domain = 1 if probs[1] >= probs[0] else 0
            if is_in_domain == 0:
                logger.info(f"Consulta fuera de dominio: {query.text[:50]}...")
                return {
                    "question": query.text,
                    "response": "La pregunta está fuera del dominio legal de tránsito.",
                    "is_domain": False,
                    "decision": "out_of_domain"
                }
        except Exception as e:
            logger.error(f"Error en Clasificador: {e}")
            raise HTTPException(status_code=500, detail="Error procesando clasificación")

        # 2. EMBEDDING & QA CACHE
        try:
            q_emb = get_embedding(query.text)
            qa_hit, qa_score = search_qa_cache(q_emb)
            
            if qa_hit is not None:
                logger.info(f"Hit en QA Cache (Score: {qa_score:.4f})")
                return {
                    "question": query.text,
                    "response": qa_hit["respuesta"],
                    "decision": "qa_cache",
                    "qa_score": qa_score
                }
        except Exception as e:
            logger.warning(f"Fallo en QA Cache: {e}. Continuando con RAG...")

        # 3. RAG - RERANKER
        try:
            results = search_ley(q_emb, TOP_K)

            if len(results) > 1 and results[0].score < SECURITY:
                results = rerank(query.text, results)
                 
                for r in results:
                    logger.info(
                        f"Qdrant: {getattr(r, 'original_score', r.score):.4f} "
                        f"| Rerank: {getattr(r, 'rerank_score', r.score):.4f}"
                    )

            results = results[:RERANK_TOP_K]

            top_scores = [hit.score for hit in results]

            top1_score = top_scores[0] if len(top_scores) > 0 else 0
            top2_score = top_scores[1] if len(top_scores) > 1 else 0
            gap = top1_score - top2_score

            logger.info(f"RAG Retrieval: Top1={top1_score:.4f}, Gap={gap:.4f}")

            context_text = "\n".join(
                f"{e.payload.get('titulo','')} Art. {e.payload.get('numero_articulo','')} - {e.payload.get('contenido','')}"
                for e in results
            )

        except Exception as e:
            logger.error(f"Error en Retrieval (Qdrant): {e}")
            raise HTTPException(status_code=500, detail="Error al recuperar contexto legal")
        

        # 4. LLM GENERATION
        try:
            prompt = f"<s>[INST] {SYSTEM_PROMPT}\n\nCONTEXTO:\n{context_text}\n\nPREGUNTA:\n{query.text} [/INST]"
            
            future = asyncio.get_running_loop().create_future()
            await state.llm_queue.put({
                "prompt": prompt,
                "sampling_params": SamplingParams(
                    max_tokens=MAX_NEW_TOKENS,
                    temperature=TEMPERATURE,
                    stop=["[/INST]", "</s>"]
                ),
                "future": future
            })

            generated_text = await future
        except Exception as e:
            logger.error(f"Error en generación LLM: {e}")
            raise HTTPException(status_code=503, detail="Servicio de generación no disponible")

        # 5. AUTO-CACHE
        try:
            if should_autocache(top_scores, generated_text, context_text):
                logger.info("Guardando respuesta en QA Cache (Auto-cache)...")
                asyncio.create_task(append_qa_cache(query.text, generated_text, q_emb))
        except Exception as e:
            logger.warning(f"No se pudo guardar en Auto-cache: {e}")

        return {
            "question": query.text,
            "response": generated_text,
            "is_domain": True,
            "decision": "rag"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error no controlado en process_query: {e}", exc_info=True)
        return {"error": "Internal Server Error", "detail": str(e)}