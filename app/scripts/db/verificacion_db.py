# import json
# from app.core.config import DATASET_FILE


# REQUIRED_FIELDS = [
#     "titulo",
#     "numero_articulo",
#     "parte",
#     "contenido",
#     "categoria",
#     "tema",
#     "resumen_semantico",
#     "palabras_claves",
#     "contexto_expandido",
#     "passage"
# ]

# def verificar_documento(doc, idx):
#     errores = []

#     for field in REQUIRED_FIELDS:
#         if field not in doc:
#             errores.append(f"Falta campo: {field}")
#         elif not doc[field]:
#             errores.append(f"Campo vacío: {field}")

#     if "palabras_claves" in doc and not isinstance(doc["palabras_claves"], list):
#         errores.append("palabras_claves debe ser una lista")

#     return errores


# def verificar_dataset(path):
#     total_errores = 0
#     total_docs = 0

#     with open(path, "r", encoding="utf-8") as f:
#         for i, line in enumerate(f):
#             line = line.strip()
#             if not line:
#                 continue

#             try:
#                 doc = json.loads(line)
#                 total_docs += 1
#             except Exception as e:
#                 print(f"Error parseando línea {i}: {e}")
#                 continue

#             errores = verificar_documento(doc, i)
#             if errores:
#                 print(f"\nDocumento {i} tiene errores:")
#                 for e in errores:
#                     print(" -", e)
#                 total_errores += 1

#     print("\nResumen:")
#     print("Documentos analizados:", total_docs)
#     print("Documentos con errores:", total_errores)

#     if total_errores == 0:
#         print("Dataset correcto. Sin errores estructurales.")


# if __name__ == "__main__":
#     verificar_dataset(DATASET_FILE)





import json
from app.core.config import DATASET_FILE

with open(DATASET_FILE, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        doc = json.loads(line)
        print(doc.keys())
        break