import uvicorn
import warnings
import logging
import os
from app.routes.api import app
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.auth.routes import router as auth_router
from fastapi import Request

app.include_router(auth_router)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Main")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://seguridadvial.codepyhub.com", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


if __name__ == "__main__":
    """
    Punto de entrada principal del servidor RAG.
    
    Responsabilidades:
    1. Silenciar advertencias de deprecación de librerías externas (Mistral/vLLM).
    """
    warnings.filterwarnings("ignore")

    logger.info("Iniciando servidor Uvicorn...")

    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=True,
            proxy_headers=True, 
            forwarded_allow_ips="*",
            server_header=False
        )

    except Exception as e:
        logger.error(f"El servidor no pudo iniciarse: {e}")
    finally:
        logger.info("Servidor finalizado.")