import uvicorn
import warnings
import logging
from app.routes.api import app


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Main")

if __name__ == "__main__":
    """
    Punto de entrada principal del servidor RAG.
    
    Responsabilidades:
    1. Silenciar advertencias de deprecación de librerías externas (Mistral/vLLM).
    2. Levantar el servidor ASGI Uvicorn en el puerto 8000.
    3. Servir como orquestador para el objeto 'app' definido en la capa de rutas.
    """
    warnings.filterwarnings("ignore")
    
    logger.info("Iniciando servidor Uvicorn...")

    try:
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000,
            log_level="info",
            access_log=True  
        )
        
    except Exception as e:
        logger.error(f"El servidor no pudo iniciarse: {e}")
    finally:
        logger.info("Servidor finalizado.")