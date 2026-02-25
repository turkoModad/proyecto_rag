import asyncio
import torch
import gc
import logging
import time
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, model_validator
from vllm import SamplingParams
from contextlib import asynccontextmanager
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.service.embedding import get_embedding
from app.engine.auto_cache import should_autocache, append_qa_cache
from app.core.variables_locales import state
from app.core.config import (
    TOP_K, DEVICE, SYSTEM_PROMPT, MAX_NEW_TOKENS,
    TEMPERATURE, SECURITY, RERANK_TOP_K, SIM_CTX
)
from app.core.model_loader import cargar_modelos
from app.engine.generator import llm_batch_worker
from app.db.vector_client import ensure_qa_collection
from app.db.vector_operations import (
    collection_is_empty,
    search_ley,
    search_qa_cache,
    load_dataset_to_qdrant
)
from app.service.reranker import rerank
from app.auth.dependencies import get_current_user, get_db
from app.auth.service import count_user_queries, count_anonymous_queries, log_query
from app.auth.init_db import (
    create_database_if_not_exists,
    create_tables,
    close_db_connections
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("APIRoutes")


# ===============================
# LIFESPAN
# ===============================
@asynccontextmanager
async def lifespan(app: FastAPI):

    try:
        logger.info("Iniciando DB...")
        await create_database_if_not_exists()
        await create_tables()

        logger.info("Iniciando servicios RAG...")
        cargar_modelos()
        ensure_qa_collection()

        if collection_is_empty():
            logger.info("Base de datos vacía. Iniciando ingesta de dataset...")
            load_dataset_to_qdrant()

        app.state.worker_task = asyncio.create_task(llm_batch_worker())

        logger.info("Sistema RAG listo y Worker en ejecución.")

    except Exception as e:
        logger.error(f"Fallo crítico en el arranque: {e}", exc_info=True)
        raise

    yield

    logger.info("Cerrando servicios...")

    app.state.worker_task.cancel()
    try:
        await app.state.worker_task
    except asyncio.CancelledError:
        logger.info("Worker detenido correctamente.")

    await close_db_connections()

    # Limpieza GPU
    state.clf_model = None
    state.llm = None

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logger.info("Sistema cerrado correctamente.")


app = FastAPI(lifespan=lifespan)


# ===============================
# MODELO REQUEST
# ===============================
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


# ===============================
# ENDPOINT PRINCIPAL
# ===============================
@app.post("/ask")
async def process_query(
    request: Request,
    query: Query,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        # ===============================
        # METADATA VISITOR
        # ===============================
        start_time = time.time()

        ip_address = (
            request.headers.get("CF-Connecting-IP")  
            or request.headers.get("x-forwarded-for")
            or request.client.host
        )
        user_agent = request.headers.get("user-agent")

        # ===============================
        # CONTROL DE USO ANONIMO Y DE PLAN
        # ===============================
        if current_user is None:
            # Usuario anónimo
            anon_count = await count_anonymous_queries(db, ip_address, "/ask")
            logger.info(f"Intento de consulta anónima #{anon_count + 1} desde {ip_address}")

            if anon_count >= 5:
                raise HTTPException(
                    status_code=401,
                    detail="Ha alcanzado el límite de 5 consultas. Por favor, regístrese o inicie sesión para continuar."
                )
        else:
            # Usuario registrado
            logger.info(f"Usuario {current_user['sub']} - Role: {current_user['role']}")
            
            if current_user["role"] == "free":
                count = await count_user_queries(db, current_user["sub"])
                if count >= 20:  
                    logger.warning("Usuario FREE alcanzó el límite de 20 consultas")
                    raise HTTPException(
                        status_code=403,
                        detail="Límite de 20 consultas alcanzado. Actualice su plan para continuar."
                    )

        # ===============================
        # 1. EMBEDDING & QA CACHE
        # ===============================
        qa_hit = None
        qa_score = 0
        sim_ctx = 0
        
        try:
            q_emb = get_embedding(query.text)
            qa_hit, qa_score = search_qa_cache(q_emb)

            if qa_hit is not None:
                logger.info(f"Hit en QA Cache candidato (Score: {qa_score:.4f})")

                contexto_cache = qa_hit.get("contexto")

                if contexto_cache:
                    emb_context_cache = get_embedding(contexto_cache)

                    sim_ctx = float(
                        cosine_similarity([q_emb], [emb_context_cache])[0][0]
                    )

                    logger.info(f"Validación coherencia cache sim_ctx={sim_ctx:.4f}")

                    if sim_ctx >= SIM_CTX:
                        logger.info("Cache válido: respuesta devuelta desde QA Cache")
                        logger.info(f"Pregunta cacheada original: {qa_hit.get('pregunta')}")
                        end_time = time.time()
                        response_time_ms = int((end_time - start_time) * 1000)

                        generated_text = qa_hit["respuesta"]
                        tokens_generated = len(generated_text.split())

                        await log_query(
                            db=db,
                            user_id=current_user["sub"] if current_user else None,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            question=query.text,
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
                            "question": query.text,
                            "response": qa_hit["respuesta"],
                            "decision": "qa_cache",
                            "qa_score": qa_score,
                            "ctx_validation": sim_ctx
                        }
                    else:
                        logger.info("Cache descartado: contexto no coherente")

        except Exception as e:
            logger.warning(f"Fallo en QA Cache: {e}. Continuando...")

        # ===============================
        # 2. CLASIFICADOR DOMINIO
        # ===============================
        try:
            inputs = state.clf_tokenizer(
                query.text,
                return_tensors="pt",
                truncation=True
            ).to(DEVICE)

            with torch.no_grad():
                logits = state.clf_model(**inputs).logits
                probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

            is_in_domain = 1 if probs[1] >= probs[0] else 0

            if is_in_domain == 0:
                logger.info(f"Consulta fuera de dominio: {query.text[:50]}...")
                end_time = time.time()
                response_time_ms = int((end_time - start_time) * 1000)

                generated_text = "La pregunta está fuera del dominio legal de tránsito."
                tokens_generated = len(generated_text.split())

                await log_query(
                    db=db,
                    user_id=current_user["sub"] if current_user else None,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    question=query.text,
                    response=generated_text,
                    decision="out_of_domain",
                    tokens_generated=tokens_generated,
                    response_time_ms=response_time_ms,
                    endpoint="/ask",
                    model_used="classifier"
                )

                return {
                    "question": query.text,
                    "response": generated_text,
                    "is_domain": False,
                    "decision": "out_of_domain"
                }

        except Exception as e:
            logger.error(f"Error en Clasificador: {e}")
            raise HTTPException(status_code=500, detail="Error procesando clasificación")

        # ===============================
        # 3. RAG - RERANKER
        # ===============================
        results = []
        top1_score = 0
        
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

        # ===============================
        # 4. LLM GENERATION
        # ===============================
        try:
            prompt = f"""
            {SYSTEM_PROMPT}

            CONTEXTO:
            {context_text}

            PREGUNTA:
            {query.text}

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

            generated_text = await future

        except Exception as e:
            logger.error(f"Error en generación LLM: {e}")
            raise HTTPException(status_code=503, detail="Servicio de generación no disponible")

        # ===============================
        # 5. AUTO-CACHE
        # ===============================
        grounding_score = 0.0
        
        try:
            autocache_decision = should_autocache(top_scores, generated_text, context_text)

            if isinstance(autocache_decision, tuple):
                do_cache, grounding_score = autocache_decision
            else:
                do_cache = autocache_decision
                grounding_score = 0.0

            if do_cache:
                retrieval_score = top_scores[0] if top_scores else 0.0

                logger.info("Guardando respuesta en QA Cache (Auto-cache)...")

                asyncio.create_task(
                    append_qa_cache(
                        question=query.text,
                        answer=generated_text,
                        context_text=context_text,
                        embedding=q_emb,
                        grounding_score=grounding_score,
                        retrieval_score=retrieval_score
                    )
                )

        except Exception as e:
            logger.warning(f"No se pudo guardar en Auto-cache: {e}")
        
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        tokens_generated = len(generated_text.split())

        # ===============================
        # 6. REGISTRO FINAL
        # ===============================
        await log_query(
            db=db,
            user_id=current_user["sub"] if current_user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            question=query.text,
            response=generated_text,
            decision="rag",
            tokens_generated=tokens_generated,
            response_time_ms=response_time_ms,
            endpoint="/ask",
            model_used="llm",
            temperature=TEMPERATURE,
            top_k_retrieved=len(results),
            retrieval_score=top1_score,
            grounding_score=grounding_score
        )

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


# ===============================
# VALIDATION HANDLER
# ===============================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Error de validación en {request.url}: {exc.body}")
    logger.error(f"Detalles: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )