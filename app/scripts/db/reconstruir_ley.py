import os
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import json
import uuid
import logging
import numpy as np
import torch
import warnings

from transformers import AutoTokenizer, AutoModel
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

from app.core.config import (
    QDRANT_HOST,
    QDRANT_PORT,
    QDRANT_API_KEY,
    COLLECTION_LEY,
    EMBEDDING,
    DEVICE,
    DATASET_FILE,
    EMB_DIM
)

# Evitar warning de conexión insegura en desarrollo
warnings.filterwarnings("ignore", message=".*Api key is used with an insecure connection.*")

# ==========================================
# CONFIG
# ==========================================

BATCH_SIZE = 32

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RebuildLeyEnriquecida")
logging.getLogger("httpx").setLevel(logging.WARNING)

# ==========================================
# CARGAR MODELO EMBEDDING
# ==========================================

logger.info(f"Cargando modelo embedding desde: {EMBEDDING}")
logger.info(f"Usando dispositivo: {DEVICE}")

tokenizer = AutoTokenizer.from_pretrained(EMBEDDING)
model = AutoModel.from_pretrained(EMBEDDING).to(DEVICE).eval()

logger.info("Modelo cargado correctamente")

# ==========================================
# NORMALIZACIÓN L2
# ==========================================

def normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm

# ==========================================
# EMBEDDING CORRECTO PARA DOCUMENTOS
# ==========================================

def get_passage_embedding(text: str) -> list:
    formatted_text = f"passage: {text}"

    inputs = tokenizer(
        formatted_text,
        return_tensors="pt",
        truncation=True,
        max_length=512
    ).to(DEVICE)

    with torch.no_grad():
        outputs = model(**inputs)
        emb = outputs.last_hidden_state.mean(dim=1)

    emb_np = emb.cpu().numpy().flatten()
    emb_np = normalize(emb_np)

    return emb_np.tolist()

# ==========================================
# CONSTRUIR PASSAGE ENRIQUECIDO
# ==========================================

def build_passage(doc: dict) -> str:

    partes = []

    if doc.get("numero_articulo"):
        partes.append(f"Artículo {doc['numero_articulo']} de la Ley 24.449")

    if doc.get("categoria"):
        partes.append(f"Categoría: {doc['categoria']}")

    if doc.get("tema"):
        partes.append(f"Tema: {doc['tema']}")

    if doc.get("resumen_semantico"):
        partes.append(f"Resumen: {doc['resumen_semantico']}")

    if doc.get("palabras_claves"):
        keywords = ", ".join(doc["palabras_claves"])
        partes.append(f"Palabras clave: {keywords}")

    if doc.get("contenido"):
        partes.append(f"Texto normativo: {doc['contenido']}")

    if doc.get("contexto_expandido"):
        partes.append(f"Contexto: {doc['contexto_expandido']}")

    return "\n".join(partes).strip()

# ==========================================
# RECONSTRUIR BASE VECTORIAL
# ==========================================

def reconstruir_db():

    logger.info("Conectando a Qdrant...")

    client = QdrantClient(
        url=f"http://{QDRANT_HOST}:{QDRANT_PORT}",
        api_key=QDRANT_API_KEY
    )

    # --------------------------------------
    # BORRAR Y CREAR COLECCIÓN (forma moderna)
    # --------------------------------------

    if client.collection_exists(COLLECTION_LEY):
        logger.info(f"La colección {COLLECTION_LEY} existe. Eliminando...")
        client.delete_collection(COLLECTION_LEY)

    logger.info(f"Creando colección: {COLLECTION_LEY}")

    client.create_collection(
        collection_name=COLLECTION_LEY,
        vectors_config=VectorParams(
            size=EMB_DIM,
            distance=Distance.COSINE
        ),
    )

    logger.info("Colección creada correctamente")

    puntos = []
    total_procesados = 0
    descartados = 0

    logger.info("Iniciando indexación...")

    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        for line in f:

            line = line.strip()
            if not line:
                continue

            try:
                doc = json.loads(line)

                passage = build_passage(doc)

                if not passage:
                    descartados += 1
                    continue

                vector = get_passage_embedding(passage)

                payload = doc.copy()
                payload["passage"] = passage

                puntos.append(
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=vector,
                        payload=payload
                    )
                )

                total_procesados += 1

                if len(puntos) >= BATCH_SIZE:
                    client.upsert(
                        collection_name=COLLECTION_LEY,
                        points=puntos
                    )
                    logger.info(f"Insertados {total_procesados} documentos...")
                    puntos = []

            except Exception as e:
                descartados += 1
                logger.error(f"Error procesando documento {total_procesados}: {e}")

    # Insertar batch final
    if puntos:
        client.upsert(
            collection_name=COLLECTION_LEY,
            points=puntos
        )

    collection_info = client.get_collection(COLLECTION_LEY)

    logger.info("===================================")
    logger.info("INDEXACIÓN FINALIZADA")
    logger.info(f"Documentos procesados: {total_procesados}")
    logger.info(f"Documentos descartados: {descartados}")
    logger.info(f"Puntos en Qdrant: {collection_info.points_count}")
    logger.info("===================================")

# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":
    reconstruir_db()