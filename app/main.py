import multiprocessing as mp
mp.set_start_method("spawn", force=True)
import torch
torch.multiprocessing.set_start_method("spawn", force=True)
import os
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"

import gc
import asyncio
import logging
import warnings
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.routes.ask import router as ask_router
from app.auth.routes import router as auth_router
from app.auth.init_db import (
    create_database_if_not_exists,
    create_tables,
    close_db_connections
)

from app.core.model_loader import cargar_modelos
from app.core.variables_locales import state
from app.engine.generator import llm_batch_worker
from app.db.vector_client import ensure_qa_collection
from app.db.vector_operations import (
    collection_is_empty,
    load_dataset_to_qdrant
)
from app.routes import seo
from app.routes.usage import router as usage_router
from app.routes.faq import router as faq_router


# LOGGING
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("Main")


# LIFESPAN
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

    # SHUTDOWN 
    logger.info("Cerrando servicios...")

    app.state.worker_task.cancel()
    try:
        await app.state.worker_task
    except asyncio.CancelledError:
        logger.info("Worker detenido correctamente.")

    await close_db_connections()
    

    # LIMPIEZA GPU
    state.clf_model = None
    state.llm = None

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    logger.info("Sistema cerrado correctamente.")


# APP
app = FastAPI(
    title="Seguridad Vial API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(ask_router)
app.include_router(auth_router)
app.include_router(seo.router)
app.include_router(usage_router)
app.include_router(faq_router)


# CORS
ALLOWED_ORIGINS = [
    "https://seguridadvial.codepyhub.com",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# FRONTEND
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
STATIC_DIR = os.path.join(BASE_DIR, "static")


@app.get("/googledc5eef5fbf5f93f5.html")
async def google_verify():
    return FileResponse(
        os.path.join(STATIC_DIR, "googledc5eef5fbf5f93f5.html")
    )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(STATIC_DIR, "favicon.ico"))


if os.path.exists(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
else:
    logger.warning("Directorio frontend no encontrado.")


if __name__ == "__main__":
    logger.info("Ejecutando servidor...")
    warnings.filterwarnings("ignore")

    try:
        uvicorn.run(
            "app.main:app",  
            host="0.0.0.0",
            port=8000,
            reload=False,
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="*",
            server_header=False,
        )

    except Exception as e:
        logger.error(f"El servidor no pudo iniciarse: {e}")
    finally:
        logger.info("Servidor finalizado.")