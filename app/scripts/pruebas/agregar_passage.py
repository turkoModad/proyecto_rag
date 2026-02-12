import json
import os
from app.core.config import DATASET_FILE


def construir_passage(doc):
    palabras = ", ".join(doc.get("palabras_claves", []))

    return (
        f"Artículo {doc.get('numero_articulo','')} de la Ley 24.449\n"
        f"Categoría: {doc.get('categoria','')}\n"
        f"Tema: {doc.get('tema','')}\n"
        f"Resumen: {doc.get('resumen_semantico','')}\n"
        f"Palabras clave: {palabras}\n"
        f"Texto normativo: {doc.get('contenido','')}\n"
        f"Contexto: {doc.get('contexto_expandido','')}"
    )


def procesar():
    documentos = []
    total = 0

    # Leer todo en memoria primero
    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        for line in f:
            doc = json.loads(line)
            if "passage" not in doc:
                doc["passage"] = construir_passage(doc)
            documentos.append(doc)
            total += 1

    # Sobrescribir el mismo archivo
    with open(DATASET_FILE, "w", encoding="utf-8") as f:
        for doc in documentos:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"Dataset actualizado correctamente.")
    print(f"Documentos procesados: {total}")


if __name__ == "__main__":
    procesar()