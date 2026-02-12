import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import torch
import numpy as np
import logging
from transformers import AutoTokenizer, AutoModel
from qdrant_client import QdrantClient

from app.core.config import (
    DEVICE,
    EMBEDDING,
    QDRANT_API_KEY,
    QDRANT_HOST,
    QDRANT_PORT,
    COLLECTION_QA,
    COLLECTION_LEY
)

TOP_K = 3

# ==============================
# LOGGING
# ==============================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DebugQdrant")


# ==============================
# EMBEDDER
# ==============================

class E5Embedder:

    def __init__(self, model_path):
        logger.info(f"Cargando modelo embedding desde: {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path).to(DEVICE)
        self.model.eval()
        logger.info(f"Modelo cargado en {DEVICE}")

    def embed(self, texts):

        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(DEVICE)

        with torch.no_grad():
            outputs = self.model(**inputs)

        embeddings = outputs.last_hidden_state[:, 0]
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

        return embeddings.cpu().numpy()


# ==============================
# DISTANCIA
# ==============================

def distancia(v1, v2):
    return np.linalg.norm(v1 - v2)


# ==============================
# CONSULTA A QDRANT
# ==============================

def buscar_en_qdrant(client, collection, query_vector, top_k=TOP_K):

    resultados = client.query_points(
        collection_name=collection,
        query=query_vector.tolist(),
        limit=top_k,
        with_payload=True,
        with_vectors=True
    )

    return resultados.points


# ==============================
# IMPRESIÓN RESULTADOS
# ==============================

def mostrar_resultados(nombre, resultados, emb_query):

    print("\n" + "="*80)
    print(f"RESULTADOS EN COLECCIÓN: {nombre}")
    print("="*80)

    scores = []

    for rank, r in enumerate(resultados, start=1):

        score = r.score
        vector_db = np.array(r.vector)
        dist = distancia(emb_query, vector_db)
        scores.append(score)

        payload = r.payload

        print(f"\nRank {rank}")
        print(f"Score Qdrant: {score:.4f}")
        print(f"Distancia euclidiana: {dist:.4f}")

        # Mostrar campos según colección
        if "pregunta" in payload:
            print(f"Pregunta:\n{payload.get('pregunta')}")
            print(f"Respuesta:\n{payload.get('respuesta')}")

        elif "passage" in payload:
            print(f"Artículo:\n{payload.get('passage')[:400]}...")

        print("-"*60)

    if len(scores) > 1:
        gap = scores[0] - scores[1]
        print(f"\nGap Rank1-Rank2: {gap:.4f}")

        if gap < 0.02:
            print("Recuperación ambigua")
        elif scores[0] < 0.60:
            print("Score bajo → revisar embeddings o chunking")
        else:
            print("Recuperación consistente")


# ==============================
# MAIN
# ==============================

def main():

    query = "¿Cuándo pueden retener un vehículo?"
    query_e5 = [f"query: {query}"]

    # Embedding
    embedder = E5Embedder(EMBEDDING)
    emb_query = embedder.embed(query_e5)[0]

    # Cliente Qdrant
    client = QdrantClient(
        url=f"http://{QDRANT_HOST}:{QDRANT_PORT}",
        api_key=QDRANT_API_KEY
    )

    print("\n" + "="*80)
    print(f"QUERY:\n{query}")
    print("="*80)

    # QA
    resultados_qa = buscar_en_qdrant(client, COLLECTION_QA, emb_query)
    mostrar_resultados("QA", resultados_qa, emb_query)

    # LEY
    resultados_ley = buscar_en_qdrant(client, COLLECTION_LEY, emb_query)
    mostrar_resultados("LEY", resultados_ley, emb_query)


if __name__ == "__main__":
    main()