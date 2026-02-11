import os
from qdrant_client import QdrantClient
from app.core.config import QDRANT_API_KEY, QDRANT_HOST, COLLECTION_QA, QDRANT_PORT, COLLECTION_LEY
import logging
import warnings

warnings.filterwarnings("ignore", message=".*Api key is used with an insecure connection.*")

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("Maintenance")


client = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}", api_key=QDRANT_API_KEY)

def consultar_todo_con_conteo(collection_name):
    info_conteo = client.count(collection_name=collection_name, exact=True)
    total_en_db = info_conteo.count
    print(f"--- Reporte de Colección: {collection_name} ---")
    print(f"Total de puntos reportados por la DB: {total_en_db}")
    print("-" * 40)

    puntos_recuperados = 0
    offset = None
    
    while True:
        puntos, offset = client.scroll(
            collection_name=collection_name,
            limit=100,  
            with_payload=True,
            with_vectors=False,
            offset=offset
        )
        
        for punto in puntos:
            puntos_recuperados += 1
            print(f"[{puntos_recuperados}] ID: {punto.id} - Pregunta: {punto.payload.get('pregunta')} - Respuesta: {punto.payload.get('respuesta')}")

        if offset is None:
            break

    print("-" * 40)
    print(f"Proceso finalizado. Se listaron {puntos_recuperados} puntos con éxito.")

consultar_todo_con_conteo(COLLECTION_QA)