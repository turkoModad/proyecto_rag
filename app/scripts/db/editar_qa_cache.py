import sys
from uuid import uuid4
import torch
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from app.core.config import QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY, COLLECTION_QA, EMBEDDING

# ----------------------------
# Embeddings
# ----------------------------
emb_model = None
emb_tokenizer = None

try:
    from app.core.variables_locales import state
    if hasattr(state, 'emb_model') and state.emb_model is not None:
        emb_model = state.emb_model
        emb_tokenizer = state.emb_tokenizer
        print("Usando embeddings cargados en memoria")
except (ImportError, AttributeError):
    pass

if emb_model is None or emb_tokenizer is None:
    from transformers import AutoTokenizer, AutoModel
    print("App apagada o modelo no disponible, cargando embeddings en caliente...")
    emb_tokenizer = AutoTokenizer.from_pretrained(EMBEDDING)
    emb_model = AutoModel.from_pretrained(
        EMBEDDING,
        dtype=torch.float16,
        device_map={"": "cuda:0"}
    ).eval()
    print("Modelo de embeddings cargado en caliente")

def get_embedding(texto):
    try:
        device = next(emb_model.parameters()).device
        
        emb_model.eval()
        with torch.no_grad():
            tokens = emb_tokenizer(texto, return_tensors="pt", truncation=True, max_length=512).to(device)
            outputs = emb_model(**tokens)

            if hasattr(outputs, "last_hidden_state"):
                vector = outputs.last_hidden_state.mean(dim=1)
            else:
                raise ValueError("El modelo no tiene 'last_hidden_state'")

            vector = vector.detach().cpu().float().squeeze(0)
            if vector.dim() == 0:
                vector = vector.unsqueeze(0)
            vector_list = vector.tolist()

            if not isinstance(vector_list, list) or len(vector_list) == 0:
                raise ValueError("El embedding generado no es una lista válida")

            return vector_list
    except Exception as e:
        raise RuntimeError(f"Error generando embedding: {e}")

# ----------------------------
# Conexión a Qdrant
# ----------------------------
client = QdrantClient(
    url=f"http://{QDRANT_HOST}:{QDRANT_PORT}",
    api_key=QDRANT_API_KEY
)

# ----------------------------
# Funciones de búsqueda y edición
# ----------------------------
def buscar_por_texto(texto):
    print("\nBuscando coincidencias...\n")
    results = client.scroll(
        collection_name=COLLECTION_QA,
        with_payload=True,
        with_vectors=True, 
        limit=200
    )

    coincidencias = []
    for point in results[0]:
        pregunta = point.payload.get("pregunta", "")
        if texto.lower() in pregunta.lower():
            coincidencias.append(point)

    if not coincidencias:
        print("No se encontraron coincidencias.")
        return None

    for i, point in enumerate(coincidencias):
        print(f"[{i}] ID: {point.id}")
        print("Pregunta:", point.payload.get("pregunta"))
        print("Respuesta:", point.payload.get("respuesta"))
        print("-" * 60)

    return coincidencias

def editar_registro(point):
    print("\n--- Edición ---")
    nueva_pregunta = input("Nueva pregunta (ENTER para mantener actual): ").strip()
    nueva_respuesta = input("Nueva respuesta (ENTER para mantener actual): ").strip()

    pregunta_final = nueva_pregunta if nueva_pregunta else point.payload["pregunta"]
    respuesta_final = nueva_respuesta if nueva_respuesta else point.payload["respuesta"]

    if nueva_pregunta:
        try:
            print("\nActualizando embedding...")
            nuevo_vector = get_embedding(pregunta_final)
        except Exception as e:
            print(f"Error: {e}")
            return
    else:
        nuevo_vector = point.vector

    client.upsert(
        collection_name=COLLECTION_QA,
        points=[
            PointStruct(
                id=point.id,
                vector=nuevo_vector,
                payload={
                    "pregunta": pregunta_final,
                    "respuesta": respuesta_final
                }
            )
        ]
    )
    print("Registro actualizado correctamente")

def agregar_registro():
    print("\n--- Nuevo Registro ---")
    nueva_pregunta = input("Ingrese la pregunta: ").strip()
    nueva_respuesta = input("Ingrese la respuesta: ").strip()

    if not nueva_pregunta or not nueva_respuesta:
        print("Pregunta y respuesta son obligatorias.")
        return

    try:
        nuevo_vector = get_embedding(nueva_pregunta)
    except Exception as e:
        print(f"Error: {e}")
        return

    nuevo_id = str(uuid4())

    client.upsert(
        collection_name=COLLECTION_QA,
        points=[
            PointStruct(
                id=nuevo_id,
                vector=nuevo_vector,
                payload={
                    "pregunta": nueva_pregunta,
                    "respuesta": nueva_respuesta
                }
            )
        ]
    )
    print("Nuevo registro agregado correctamente")

def menu():
    while True:
        print("\n===== MENÚ =====")
        print("1. Buscar y editar pregunta")
        print("2. Agregar nueva pregunta")
        print("3. Salir")
        opcion = input("Seleccione una opción [1/2/3]: ").strip()

        if opcion == "1":
            texto = input("Ingrese texto para buscar en las preguntas: ").strip()
            coincidencias = buscar_por_texto(texto)
            if coincidencias:
                try:
                    index_input = input("Seleccione el número del registro a editar (o ENTER para cancelar): ").strip()
                    if not index_input:
                        continue
                    index = int(index_input)
                    if 0 <= index < len(coincidencias):
                        editar_registro(coincidencias[index])
                    else:
                        print("Índice fuera de rango.")
                except ValueError:
                    print("Error: Debe ingresar un número válido.")

        elif opcion == "2":
            agregar_registro()

        elif opcion == "3":
            print("Saliendo...")
            break
        else:
            print("Opción inválida. Intente de nuevo.")

if __name__ == "__main__":
    menu()