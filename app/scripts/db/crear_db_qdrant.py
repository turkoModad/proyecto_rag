import os

os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import json
import uuid
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from app.core.config import QDRANT_API_KEY, QDRANT_HOST, COLLECTION_QA, QDRANT_PORT, COLLECTION_LEY, DATASET_FILE, EMBEDDING, DEVICE


BATCH_SIZE = 32


print(f"Cargando modelo en {DEVICE}...")
tokenizer = AutoTokenizer.from_pretrained(EMBEDDING)
model = AutoModel.from_pretrained(EMBEDDING).to(DEVICE).eval()

def get_embedding(text):
    text_formatted = f"passage: {text}"
    
    inputs = tokenizer(text_formatted, return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)
        emb = outputs.last_hidden_state.mean(dim=1).cpu().numpy()[0]
    
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm
    return emb.tolist()


client = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}", api_key=QDRANT_API_KEY)


# Crear o recrear colección
if not client.collection_exists(COLLECTION_LEY):
    print(f"Creando colección: {COLLECTION_LEY}")
    client.create_collection(
        collection_name=COLLECTION_LEY,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
else:
    print(f"La colección {COLLECTION_LEY} ya existe. Sumando puntos nuevos...")
    

points = []
total_procesados = 0

print("Iniciando lectura de archivo y generación de embeddings...")

with open(DATASET_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue 
        
        try:
            obj = json.loads(line)
            
            texto_para_vector = f"{obj.get('titulo', '')} {obj.get('numero_articulo', '')} {obj['contenido']}"
            
            embedding = get_embedding(texto_para_vector)
            
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload=obj
                )
            )
            total_procesados += 1

            if len(points) >= BATCH_SIZE:
                client.upsert(collection_name=COLLECTION_LEY, points=points)
                print(f">>> Insertados {total_procesados} documentos...")
                points = []
                
        except Exception as e:
            print(f"Error procesando línea {total_procesados + 1}: {e}")

if points:
    client.upsert(collection_name=COLLECTION_LEY, points=points)
    print(f">>> Insertado batch final.")

print("-" * 30)
collection_info = client.get_collection(COLLECTION_LEY)
print(f"PROCESO FINALIZADO")
print(f"Documentos leídos del archivo: {total_procesados}")
print(f"Total actual de puntos en Qdrant: {collection_info.points_count}")
print("-" * 30)