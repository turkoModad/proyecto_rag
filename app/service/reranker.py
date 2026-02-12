import torch
import numpy as np
from app.core.variables_locales import state
from app.core.config import DEVICE

def rerank(query: str, documents: list):
    """
    documents: lista de dicts con {payload, score, vector}
    Retorna documentos reordenados por score semántico cruzado.
    """

    if not documents:
        return documents

    pairs = []

    for doc in documents:
        passage = doc.payload.get("passage", "")
        pairs.append((query, passage))

    inputs = state.rerank_tokenizer(
        pairs,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt"
    ).to(DEVICE)

    with torch.no_grad():
        outputs = state.rerank_model(**inputs)
        scores = outputs.logits.squeeze(-1)

    scores = scores.detach().cpu().numpy()

    # Ordenar por score descendente
    ranked = sorted(
        zip(documents, scores),
        key=lambda x: x[1],
        reverse=True
    )

    return [doc for doc, _ in ranked]