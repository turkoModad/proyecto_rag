from fastapi import APIRouter, Depends, HTTPException
import uuid
import time
from qdrant_client.models import PointStruct

from app.service.embedding import get_embedding
from app.db.vector_client import client
from app.core.config import COLLECTION_QA
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/admin")


@router.post("/ingest_qa")
async def ingest(data: dict, user=Depends(get_current_user)):

    pregunta = data.get("pregunta")
    respuesta = data.get("respuesta")

    if not pregunta or not respuesta:
        raise HTTPException(400, "Pregunta o respuesta faltante")

    vector = get_embedding(pregunta, prefix="passage")

    if vector is None:
        raise HTTPException(500, "Error generando embedding")

    if hasattr(vector, "tolist"):
        vector = vector.tolist()

    payload = {
        "pregunta": pregunta,
        "respuesta": respuesta,
        "contexto": f"{pregunta}\n{respuesta}",
        "tipo": "qa_manual",
        "timestamp": int(time.time())
    }

    point = PointStruct(
        id=str(uuid.uuid4()),
        vector=vector,
        payload=payload
    )

    client.upsert(
        collection_name=COLLECTION_QA,
        points=[point]
    )

    return {"status": "ok"}