import numpy as np
import torch
import logging
from app.core.config import DEVICE
from app.core.variables_locales import state


logger = logging.getLogger("EmbeddingService")


# =========================
# NORMALIZACION
# =========================
def normalize(v: np.ndarray) -> np.ndarray:
    """
    Realiza la normalización L2 de un vector.
    Esencial para que la búsqueda por Distancia Coseno en Qdrant sea precisa.
    """
    norm = np.linalg.norm(v)
    if norm == 0:
        logger.warning("Se detectó un vector de norma cero durante la normalización.")
        return v
    return v / norm

# =========================
# EMBEDDING
# =========================
def get_embedding(text: str) -> np.ndarray:
    """
    Genera una representación vectorial densa de un texto usando el modelo cargado en 'state'.
    
    Proceso:
    1. Prepara el texto con el prefijo 'query: '.
    2. Realiza la inferencia en la GPU configurada.
    3. Aplica Mean Pooling sobre los estados ocultos.
    4. Normaliza el vector final antes de devolverlo.
    """
    if not text or not isinstance(text, str):
        logger.error("Se recibió un texto vacío o inválido para generar embedding.")
        return np.zeros(1024) 

    try:
        inputs = state.emb_tokenizer(
            f"query: {text}",
            return_tensors="pt",
            truncation=True,
            max_length=512
        ).to(DEVICE)

        with torch.no_grad():
            outputs = state.emb_model(**inputs)
            emb = outputs.last_hidden_state.mean(dim=1)

        # Mover a CPU y convertir a Numpy para compatibilidad con Qdrant y Sklearn
        emb_np = emb.cpu().numpy().flatten()
        
        return normalize(emb_np)

    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            logger.critical("GPU Out of Memory durante la generación de embeddings.")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        else:
            logger.error(f"Error de tiempo de ejecución en modelo de embedding: {e}")
        return np.zeros(1024)
        
    except Exception as e:
        logger.error(f"Error inesperado al generar embedding: {e}", exc_info=True)
        return np.zeros(1024)