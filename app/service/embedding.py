import numpy as np
import torch
import logging
from app.core.config import DEVICE
from app.core.variables_locales import state


logger = logging.getLogger("EmbeddingService")


# NORMALIZACION
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


# POOLING PARA E5
def average_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """
    Aplica masked mean pooling recomendado para modelos E5.
    Ignora padding correctamente.
    """
    last_hidden = last_hidden_states.masked_fill(
        ~attention_mask[..., None].bool(),
        0.0
    )
    return last_hidden.sum(dim=1) / attention_mask.sum(dim=1)[..., None]


# EMBEDDING
def get_embedding(text: str, prefix="query") -> np.ndarray:
    """
    Genera embedding usando prefijo correcto para E5.
    
    prefix:
        "query"   -> consultas
        "passage" -> documentos
    """

    if not text or not isinstance(text, str):
        logger.error("Texto inválido para embedding.")
        dim = state.emb_model.config.hidden_size
        return np.zeros(dim)

    try:
        formatted_text = f"{prefix}: {text}"

        inputs = state.emb_tokenizer(
            formatted_text,
            return_tensors="pt",
            truncation=True,
            max_length=512
        ).to(DEVICE)

        with torch.no_grad():
            outputs = state.emb_model(**inputs)
            emb = average_pool(
                outputs.last_hidden_state,
                inputs["attention_mask"]
            )

        emb_np = emb.cpu().numpy().flatten()
        emb_np = normalize(emb_np)

        return emb_np

    except Exception as e:
        logger.error(f"Error generando embedding: {e}")
        dim = state.emb_model.config.hidden_size
        return np.zeros(dim)