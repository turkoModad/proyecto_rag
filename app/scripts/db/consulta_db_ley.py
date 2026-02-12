import json
import logging
import warnings

from qdrant_client import QdrantClient
from app.core.config import (
    QDRANT_API_KEY,
    QDRANT_HOST,
    QDRANT_PORT,
    COLLECTION_LEY
)

warnings.filterwarnings("ignore", message=".*Api key is used with an insecure connection.*")

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

client = QdrantClient(
    url=f"http://{QDRANT_HOST}:{QDRANT_PORT}",
    api_key=QDRANT_API_KEY
)


def auditar_campos(collection_name, mostrar_ejemplos=3):
    """
    Verifica qué campos existen en el payload y muestra ejemplos reales.
    """

    print(f"\nAuditoría de colección: {collection_name}")
    print("-" * 50)

    puntos, _ = client.scroll(
        collection_name=collection_name,
        limit=100,
        with_payload=True,
        with_vectors=False
    )

    if not puntos:
        print("No se encontraron puntos en la colección.")
        return

    # Detectar todas las claves
    todas_las_claves = set()
    for p in puntos:
        if p.payload:
            todas_las_claves.update(p.payload.keys())

    print("\nCampos detectados en el payload:")
    for campo in sorted(todas_las_claves):
        print(" -", campo)

    print("\nEjemplos de documentos:\n")

    for i, punto in enumerate(puntos[:mostrar_ejemplos], start=1):
        print(f"--- Documento {i} ---")
        print(json.dumps(punto.payload, indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    auditar_campos(COLLECTION_LEY)