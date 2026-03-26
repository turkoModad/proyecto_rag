from fastapi import APIRouter, Depends, HTTPException
import uuid
import time

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchText
from app.service.embedding import get_embedding
from app.db.vector_client import client
from app.core.config import COLLECTION_LEY
from app.administracion.security.admin_security import require_admin


router = APIRouter(
    prefix="/vector",
    dependencies=[Depends(require_admin)]
)


@router.post("/ingest_qa_batch")
async def ingest_qa_batch(data: dict):
    """
    Endpoint optimizado para cargar múltiples registros en batch
    """
    registros = data.get("registros", [])
    
    if not registros:
        raise HTTPException(status_code=400, detail="No se enviaron registros")
    
    if len(registros) > 100:
        raise HTTPException(status_code=400, detail="Máximo 100 registros por batch")
    
    points = []
    resultados = []
    
    for registro in registros:
        pregunta = registro.get("pregunta")
        respuesta = registro.get("respuesta")
        articulo = registro.get("articulo")
        
        # Validaciones
        if not pregunta or not respuesta:
            resultados.append({
                "status": "error",
                "detail": "Pregunta o respuesta faltante",
                "pregunta": pregunta[:50] if pregunta else None
            })
            continue
        
        if len(pregunta) > 1000 or len(respuesta) > 3000:
            resultados.append({
                "status": "error", 
                "detail": "Texto demasiado largo",
                "pregunta": pregunta[:50]
            })
            continue
        
        contenido = f"Pregunta: {pregunta}\nRespuesta: {respuesta}"
        
        vector = get_embedding(contenido, prefix="passage")
        
        if vector is None:
            resultados.append({
                "status": "error",
                "detail": "Error generando embedding",
                "pregunta": pregunta[:50]
            })
            continue
        
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        
        payload = {
            "contenido": contenido,
            "contexto": contenido,
            "tipo": "faq",
            "metadata": articulo,
            "timestamp": int(time.time())
        }
        
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload=payload
        )
        
        points.append(point)
        resultados.append({
            "status": "ok",
            "id": point.id,
            "pregunta": pregunta[:50]
        })
    
    if points:
        try:
            client.upsert(
                collection_name=COLLECTION_LEY,
                points=points
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error guardando en vector DB: {str(e)}")
    
    return {
        "status": "ok",
        "total": len(registros),
        "exitosos": len(points),
        "fallidos": len(registros) - len(points),
        "resultados": resultados
    }


@router.post("/search_qa")
async def search_qa(data: dict):
    """
    Busca entradas en la colección QA por texto
    """
    texto = data.get("texto")
    limit = data.get("limit", 50)  # Límite de resultados, por defecto 50
    
    if not texto:
        raise HTTPException(status_code=400, detail="Texto de búsqueda faltante")
    
    try:
        # Opción 1: Búsqueda por scroll con filtro de texto (más simple)
        # Esto busca coincidencias exactas en el payload
        scroll_result = client.scroll(
            collection_name=COLLECTION_LEY,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="contenido",
                        match=MatchText(text=texto)
                    )
                ]
            ),
            limit=limit
        )
        
        points = scroll_result[0]  # El primer elemento son los puntos
        results = []
        
        for point in points:
            results.append({
                "id": point.id,
                "payload": point.payload,
                "vector": point.vector if hasattr(point, "vector") else None
            })
        
        return {
            "status": "ok",
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")


@router.post("/search_qa_semantic")
async def search_qa_semantic(data: dict):
    """
    Búsqueda semántica usando embeddings (más precisa)
    """
    texto = data.get("texto")
    limit = data.get("limit", 10)
    
    if not texto:
        raise HTTPException(status_code=400, detail="Texto de búsqueda faltante")
    
    try:
        # Generar embedding para el texto de búsqueda
        query_vector = get_embedding(texto, prefix="query")
        
        if query_vector is None:
            raise HTTPException(status_code=500, detail="Error generando embedding para búsqueda")
        
        if hasattr(query_vector, "tolist"):
            query_vector = query_vector.tolist()
        
        # Buscar por similitud vectorial
        search_result = client.search(
            collection_name=COLLECTION_LEY,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        results = []
        for scored_point in search_result:
            results.append({
                "id": scored_point.id,
                "payload": scored_point.payload,
                "score": scored_point.score  # Similaridad (0-1)
            })
        
        return {
            "status": "ok",
            "count": len(results),
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en búsqueda semántica: {str(e)}")


@router.post("/list_all_qa")
async def list_all_qa(data: dict = None):
    """
    Lista todas las entradas (útil para debugging)
    """
    limit = data.get("limit", 100) if data else 100
    offset = data.get("offset", 0) if data else 0
    
    try:
        scroll_result = client.scroll(
            collection_name=COLLECTION_LEY,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        points = scroll_result[0]
        next_offset = scroll_result[1]
        
        results = []
        for point in points:
            results.append({
                "id": point.id,
                "payload": point.payload
            })
        
        return {
            "status": "ok",
            "count": len(results),
            "next_offset": next_offset,
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listando entradas: {str(e)}")


@router.post("/delete_qa")
async def delete_qa(data: dict):
    """
    Elimina una entrada por su ID
    """
    point_id = data.get("id")
    
    if not point_id:
        raise HTTPException(status_code=400, detail="ID de punto faltante")
    
    try:
        client.delete(
            collection_name=COLLECTION_LEY,
            points_selector=[point_id]
        )
        return {"status": "ok", "message": f"Entrada {point_id} eliminada correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando entrada: {str(e)}")


@router.post("/delete_by_filter")
async def delete_by_filter(data: dict):
    """
    Elimina entradas que coinciden con un filtro (¡CUIDADO! puede eliminar múltiples)
    """
    field = data.get("field")
    value = data.get("value")
    
    if not field or not value:
        raise HTTPException(status_code=400, detail="Campo y valor requeridos")
    
    try:
        # Primero buscar las entradas que coinciden
        scroll_result = client.scroll(
            collection_name=COLLECTION_LEY,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key=field,
                        match=MatchText(text=value)
                    )
                ]
            ),
            limit=100  # Límite por seguridad
        )
        
        points = scroll_result[0]
        point_ids = [point.id for point in points]
        
        if not point_ids:
            return {"status": "ok", "message": "No se encontraron entradas para eliminar", "deleted": 0}
        
        # Eliminar los puntos encontrados
        client.delete(
            collection_name=COLLECTION_LEY,
            points_selector=point_ids
        )
        
        return {
            "status": "ok",
            "message": f"Se eliminaron {len(point_ids)} entradas",
            "deleted": len(point_ids),
            "ids": point_ids
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando entradas: {str(e)}")