import os

os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import torch
import numpy as np
import logging
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity
from app.core.config import EMBEDDING, DEVICE


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CompararOraciones")


class E5Embedder:
    """
    Clase para generar embeddings utilizando el modelo E5.
    Se encarga de la tokenización, inferencia y normalización L2.
    """
    def __init__(self, model_path):
        logger.info(f"Cargando modelo embedding desde: {model_path}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModel.from_pretrained(model_path).to(DEVICE)
            self.model.eval()
            logger.info(f"Modelo cargado correctamente en {DEVICE}")
        except Exception as e:
            logger.error(f"Error cargando el modelo: {e}")
            raise

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

def mostrar_similitud(nombre, matrix):
    print(f"\n=== {nombre} ===")
    for row in matrix:
        print("  ".join(f"{v:.4f}" for v in row))

def distancia(v1, v2):
    """Calcula la distancia euclidiana entre dos vectores."""
    return np.linalg.norm(v1 - v2)

def main():
    # Datos de prueba
    preguntas = [
        "¿Qué dispositivo deben tener los automotores para cortar rápidamente la energía?",
        "¿Qué tipo de bocina deben llevar los automotores y qué sonoridad debe tener?" 
    ]

    respuestas = [
        "Dispositivo para corte rápido de energía.",
        "Los vehículos en Argentina deben cumplir con ciertos límites para evitar contaminar el aire y generar ruidos excesivos. Es decir, deben emitir menos contaminantes y hacer menos ruido que lo permitido por la ley."
    ]

    preguntas_e5 = [f"query: {p}" for p in preguntas]
    respuestas_e5 = [f"passage: {r}" for r in respuestas]

    embedder = E5Embedder(EMBEDDING)

    emb_preguntas = embedder.embed(preguntas_e5)
    emb_respuestas = embedder.embed(respuestas_e5)

    # Similitud Coseno
    sim_pp = cosine_similarity(emb_preguntas, emb_preguntas)
    sim_rr = cosine_similarity(emb_respuestas, emb_respuestas)
    sim_pr = cosine_similarity(emb_preguntas, emb_respuestas)

    mostrar_similitud("Similitud Coseno Pregunta vs Pregunta", sim_pp)
    mostrar_similitud("Similitud Coseno Respuesta vs Respuesta", sim_rr)
    mostrar_similitud("Similitud Coseno Pregunta vs Respuesta", sim_pr)

    print("\n=== Distancia Preguntas ===")
    for i in range(len(emb_preguntas)):
        for j in range(i+1, len(emb_preguntas)):
            print(f"P{i} - P{j}: {distancia(emb_preguntas[i], emb_preguntas[j]):.4f}")

    print("\n=== Distancia Respuestas ===")
    for i in range(len(emb_respuestas)):
        for j in range(i+1, len(emb_respuestas)):
            print(f"R{i} - R{j}: {distancia(emb_respuestas[i], emb_respuestas[j]):.4f}")

if __name__ == "__main__":
    main()