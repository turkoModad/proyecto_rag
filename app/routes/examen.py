from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import logging
import os
import json
import random
import hashlib
from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone, timedelta


logger = logging.getLogger("Examen")
router = APIRouter(tags=["examen"])


ROUTES_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(ROUTES_DIR))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

EXAMEN_FILE = os.path.join(FRONTEND_DIR, "examen.html")

DATA_PATH = "data/preguntas_examen.jsonl"

DURACION_EXAMEN = 600  
MAX_PREGUNTAS = 100    


class Respuesta(BaseModel):
    id: int
    seleccion: int
    opciones: List[str]

class EvaluacionRequest(BaseModel):
    start_time: str
    respuestas: List[Respuesta]


def cargar_preguntas():
    preguntas = []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        for line in f:
            preguntas.append(json.loads(line))
    return preguntas

PREGUNTAS_DB = cargar_preguntas()


def generate_etag(path: str):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def build_response(file_path: str, canonical_url: str):

    if not os.path.exists(file_path):
        logger.error(f"Archivo examen no encontrado: {file_path}")
        raise FileNotFoundError(file_path)

    etag = generate_etag(file_path)

    response = FileResponse(
        file_path,
        media_type="text/html"
    )

    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["ETag"] = etag
    response.headers["X-Robots-Tag"] = "index, follow"
    response.headers["Content-Language"] = "es"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Link"] = f'<{canonical_url}>; rel="canonical"'

    return response


@router.api_route("/examen", methods=["GET", "HEAD"])
@router.api_route("/examen/", methods=["GET", "HEAD"])
async def examen_page():
    return build_response(
        EXAMEN_FILE,
        "https://seguridadvial.codepyhub.com/examen/"
    )


@router.get("/examen/data")
async def generar_examen(cantidad: int = 20):
    cantidad = max(20, min(cantidad, MAX_PREGUNTAS))  
    cantidad = min(cantidad, len(PREGUNTAS_DB))      

    seleccion = random.sample(PREGUNTAS_DB, cantidad)

    examen = []

    for p in seleccion:
        opciones = p["respuestas"].copy()
        random.shuffle(opciones)

        correcta_texto = p["correcta"]
        correcta_index = opciones.index(correcta_texto)

        examen.append({
            "id": p["id"],
            "pregunta": p["pregunta"],
            "opciones": opciones,
            "correcta_index": correcta_index,  
            "categoria": p.get("categoria"),
            "imagen": p.get("imagen", None)
        })

    return {
        "start_time": datetime.now(timezone.utc).isoformat(),
        "duracion_max": DURACION_EXAMEN,
        "preguntas": examen
    }


@router.post("/examen/evaluar")
async def evaluar(data: EvaluacionRequest):

    try:
        start_time = datetime.fromisoformat(data.start_time.replace('Z', '+00:00'))
    except:
        raise HTTPException(status_code=400, detail="start_time inválido")

    ahora = datetime.now(timezone.utc)

    if ahora - start_time > timedelta(seconds=DURACION_EXAMEN + 60):  
        return {
            "error": "Tiempo excedido",
            "resultado": 0,
            "total": len(data.respuestas)
        }

    correctas = 0

    for r in data.respuestas:
        pregunta = next((p for p in PREGUNTAS_DB if p["id"] == r.id), None)

        if not pregunta:
            continue

        opcion_seleccionada = r.opciones[r.seleccion]
        if opcion_seleccionada == pregunta["correcta"]:
            correctas += 1

    return {
        "resultado": correctas,
        "total": len(data.respuestas),
        "tiempo_valido": True
    }