import torch
import logging
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModel
from vllm import LLM
from app.core.config import (
    CLASIFICADOR, EMBEDDING, MODELO_GENERADOR, UTILIZACION_GPU, MAX_MODEL_LENGTH, RERANKER
)
from app.core.variables_locales import state


logging.getLogger("vllm").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)
logger = logging.getLogger("ModelLoader")


def cargar_modelos():
    """
    Inicializa y carga en memoria GPU todos los modelos necesarios para el pipeline RAG.
    
    Proceso:
    1. Clasificador: Carga un modelo de secuencia (Transformers) en FP16 para determinar si la consulta es de dominio legal.
    2. Embeddings: Carga el modelo de representación vectorial (Transformers) en FP16 para la búsqueda semántica en Qdrant.
    3. Generador: Inicializa el motor de inferencia masiva (vLLM) optimizando el uso de VRAM según la configuración.
    
    Nota: Se utiliza device_map='cuda:0' para asegurar la asignación en la GPU seleccionada (previamente filtrada).
    """


    # --- 1. CARGA DEL CLASIFICADOR ---
    try:
        logger.info("Cargando modelo: [CLASIFICADOR]")
        state.clf_tokenizer = AutoTokenizer.from_pretrained(CLASIFICADOR, trust_remote_code=True)
        state.clf_model = AutoModelForSequenceClassification.from_pretrained(
            CLASIFICADOR,
            dtype=torch.float16,
            device_map={"": "cuda:0"}
        ).eval()
    except Exception as e:
        logger.error(f"Error crítico cargando Clasificador: {e}")
        raise  


    # --- 2. CARGA DE EMBEDDINGS ---
    try:
        logger.info("Cargando modelo: [EMBEDDINGS]")
        state.emb_tokenizer = AutoTokenizer.from_pretrained(
            EMBEDDING,
            local_files_only=True
        )
        state.emb_model = AutoModel.from_pretrained(
            EMBEDDING,
            dtype=torch.float16,
            device_map={"": "cuda:0"}
        ).eval() 
    except Exception as e:
        logger.error(f"Error crítico cargando Embeddings: {e}")
        raise


    # --- 3. CARGA DEL RERANKER ---
    try:
        logger.info("Cargando modelo: [RERANKER]")
        state.rerank_tokenizer = AutoTokenizer.from_pretrained(RERANKER)
        state.rerank_model = AutoModelForSequenceClassification.from_pretrained(
            RERANKER,
            dtype=torch.float16,
            device_map={"": "cuda:0"}
        ).eval()

        torch.set_grad_enabled(False)

    except Exception as e:
        logger.error(f"Error crítico cargando Reranker: {e}")
        raise


    # --- 4. CARGA DEL GENERADOR (vLLM) ---
    try:
        logger.info("Cargando modelo: [GENERADOR LLM]")
        state.llm = LLM(
            model=MODELO_GENERADOR,
            gpu_memory_utilization=UTILIZACION_GPU,
            max_model_len=MAX_MODEL_LENGTH,
            disable_log_stats=True
        )
    except torch.cuda.OutOfMemoryError:
        logger.error("Error: Memoria VRAM insuficiente para vLLM. Reduce UTILIZACION_GPU.")
        raise
    except Exception as e:
        logger.error(f"Error crítico cargando vLLM: {e}")
        raise

    logger.info("=== Todos los modelos se cargaron exitosamente en la GPU ===")