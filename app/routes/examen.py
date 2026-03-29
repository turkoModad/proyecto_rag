from fastapi import APIRouter, HTTPException, Depends, Request
import logging
import json
import random
import secrets
from uuid import UUID
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc

from app.auth.database import get_db
from app.auth.models import User, ExamAttempt, ExamSession, ExamLog
from app.auth.dependencies import get_current_user_db, get_or_create_anon_id

logger = logging.getLogger("Examen")
router = APIRouter(tags=["examen"])

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
DURACION_EXAMEN = 600
MIN_RESPUESTAS_VALIDAS = 5
MIN_ANSWER_TIME = 2

DATA_PATH = "data/preguntas_examen.jsonl"

NIVELES = {
    "aprendiz": 20,
    "veterano": 40,
    "leyenda": 60
}

# ------------------------------------------------------------
# MODELOS
# ------------------------------------------------------------
class Respuesta(BaseModel):
    id: int
    seleccion: int

class EvaluacionRequest(BaseModel):
    token: str
    respuestas: List[Respuesta]
    nombre: Optional[str] = Field(None, max_length=50)

class NombreRequest(BaseModel):
    token: str
    nombre: str = Field(..., max_length=50)

class IniciarRequest(BaseModel):
    nivel: str = "veterano"

# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------
def cargar_preguntas():
    preguntas = []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        for line in f:
            preguntas.append(json.loads(line))
    return preguntas

PREGUNTAS_DB = cargar_preguntas()

def get_medalla(score, total):
    ratio = score / total
    if ratio >= 0.9:
        return "🥇"
    elif ratio >= 0.75:
        return "🥈"
    elif ratio >= 0.6:
        return "🥉"
    return ""

def is_bot(user_agent: str) -> bool:
    if not user_agent:
        return True
    ua = user_agent.lower()
    suspicious = ["headless", "puppeteer", "selenium", "curl", "wget", "bot"]
    return any(word in ua for word in suspicious)

async def log_exam_action(db, session_id, ip, ua, action, details=None):
    log = ExamLog(
        session_id=session_id,
        ip_address=ip,
        user_agent=ua,
        action=action,
        details=json.dumps(details) if details else None
    )
    db.add(log)
    await db.commit()

# ------------------------------------------------------------
# START
# ------------------------------------------------------------
@router.post("/examen/start")
async def iniciar_examen(
    request: Request,
    data: IniciarRequest,
    anon_id: str = Depends(get_or_create_anon_id),
    user: User = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_db)
):
    ip = request.client.host
    ua = request.headers.get("user-agent", "")

    if is_bot(ua):
        raise HTTPException(403, "Acceso bloqueado")

    if data.nivel not in NIVELES:
        raise HTTPException(400, "Nivel inválido")

    cantidad = min(NIVELES[data.nivel], len(PREGUNTAS_DB))
    seleccion = random.sample(PREGUNTAS_DB, cantidad)

    preguntas_cliente = []
    correctas_map = {}

    for p in seleccion:
        opciones = p["respuestas"].copy()
        random.shuffle(opciones)
        correcta_index = opciones.index(p["correcta"])

        preguntas_cliente.append({
            "id": p["id"],
            "pregunta": p["pregunta"],
            "opciones": opciones,
            "imagen": p.get("imagen")
        })

        correctas_map[p["id"]] = correcta_index

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    session = ExamSession(
        token=token,
        user_id=user.id if user else None,
        anon_id=anon_id,
        nivel=data.nivel,
        total_questions=cantidad,
        questions_data=json.dumps(preguntas_cliente),
        correct_answers=json.dumps(correctas_map),
        start_time=now,
        expires_at=now + timedelta(seconds=DURACION_EXAMEN),
        ip_address=ip,
        user_agent=ua
    )

    db.add(session)
    await db.commit()

    return {
        "token": token,
        "duracion_max": DURACION_EXAMEN,
        "start_time": now.isoformat(),
        "preguntas": preguntas_cliente
    }

# ------------------------------------------------------------
# SUBMIT (MEJORADO)
# ------------------------------------------------------------
@router.post("/examen/submit")
async def evaluar_examen(
    request: Request,
    data: EvaluacionRequest,
    anon_id: str = Depends(get_or_create_anon_id),
    user: User = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_db)
):
    ip = request.client.host
    ua = request.headers.get("user-agent", "")

    result = await db.execute(
        select(ExamSession).where(ExamSession.token == data.token)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(400, "Token inválido")

    if session.evaluated:
        raise HTTPException(400, "Ya evaluado")

    ahora = datetime.now(timezone.utc)

    if ahora > session.expires_at:
        session.evaluated = True
        await db.commit()
        return {"error": "Tiempo excedido", "resultado": 0, "total": session.total_questions}

    duracion = int((ahora - session.start_time).total_seconds())

    preguntas_originales = {
        p["id"] for p in json.loads(session.questions_data)
    }

    preguntas_enviadas = {r.id for r in data.respuestas}

    if preguntas_enviadas != preguntas_originales:
        raise HTTPException(400, "Manipulación detectada")

    correctas_map = json.loads(session.correct_answers)

    correctas = 0
    respondidas = 0

    for r in data.respuestas:
        if r.seleccion != -1:
            respondidas += 1
            if str(r.id) in correctas_map and correctas_map[str(r.id)] == r.seleccion:
                correctas += 1

    if respondidas < MIN_RESPUESTAS_VALIDAS:
        session.evaluated = True
        await db.commit()
        return {
            "error": "Muy pocas respuestas",
            "resultado": 0,
            "total": session.total_questions
        }

    # --------------------------------------------------------
    # VALIDACIONES ANTIBOT
    # --------------------------------------------------------
    is_valid = True

    if duracion < (len(preguntas_originales) * MIN_ANSWER_TIME):
        is_valid = False

    if correctas == session.total_questions and duracion < 30:
        is_valid = False

    if is_bot(ua):
        is_valid = False

    session.evaluated = True
    await db.commit()

    intento = ExamAttempt(
        user_id=user.id if user else None,
        anon_id=anon_id,
        display_name=data.nombre[:50] if data.nombre else None,
        ip_address=ip,
        score=correctas,
        total=session.total_questions,
        duration_seconds=duracion,
        start_time=session.start_time,
        completed=True,
        is_valid=is_valid,
        session_id=session.id
    )

    db.add(intento)
    await db.commit()

    return {
        "resultado": correctas,
        "total": session.total_questions,
        "duracion": duracion,
        "medalla": get_medalla(correctas, session.total_questions),
        "attempt_id": intento.id
    }

# ------------------------------------------------------------
# RANKING
# ------------------------------------------------------------
@router.get("/examen/top10/{nivel}")
async def top10_por_nivel(nivel: str, db: AsyncSession = Depends(get_db)):
    if nivel not in NIVELES:
        raise HTTPException(400, "Nivel inválido")

    total = NIVELES[nivel]

    result = await db.execute(
        select(ExamAttempt)
        .where(
            ExamAttempt.completed == True,
            ExamAttempt.is_valid == True,
            ExamAttempt.total == total,
            ExamAttempt.score >= (ExamAttempt.total * 0.6)
        )
        .order_by(desc(ExamAttempt.score), asc(ExamAttempt.duration_seconds))
        .limit(10)
    )

    return [
        {
            "nombre": r.display_name or "Anónimo",
            "score": r.score,
            "total": r.total,
            "duracion": r.duration_seconds,
            "medalla": get_medalla(r.score, r.total)
        }
        for r in result.scalars().all()
    ]

# ------------------------------------------------------------
# RANKING DETALLE
# ------------------------------------------------------------
@router.get("/examen/ranking/{attempt_id}")
async def ranking_examen(attempt_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExamAttempt).where(ExamAttempt.id == attempt_id))
    intento = result.scalar_one_or_none()

    if not intento:
        raise HTTPException(404, "Intento no encontrado")

    total = intento.total
    nivel = next((k for k, v in NIVELES.items() if v == total), None)

    result_all = await db.execute(
        select(ExamAttempt)
        .where(
            ExamAttempt.completed == True,
            ExamAttempt.is_valid == True,
            ExamAttempt.total == total,
            ExamAttempt.score >= (ExamAttempt.total * 0.6)
        )
        .order_by(desc(ExamAttempt.score), asc(ExamAttempt.duration_seconds))
    )

    all_attempts = result_all.scalars().all()

    posicion = next((i + 1 for i, x in enumerate(all_attempts) if x.id == attempt_id), None)

    return {
        "top10": [
            {
                "nombre": r.display_name or "Anónimo",
                "score": r.score,
                "total": r.total,
                "duracion": r.duration_seconds,
                "medalla": get_medalla(r.score, r.total)
            } for r in all_attempts[:10]
        ],
        "usuario": {
            "nombre": intento.display_name or "Anónimo",
            "score": intento.score,
            "total": intento.total,
            "duracion": intento.duration_seconds,
            "posicion": posicion,
            "nivel": nivel,
            "medalla": get_medalla(intento.score, intento.total)
        }
    }


@router.post("/examen/set-nombre")
async def set_nombre(
    data: NombreRequest,
    db: AsyncSession = Depends(get_db)
):
    # Buscar sesión por token
    result = await db.execute(
        select(ExamSession).where(ExamSession.token == data.token)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, "Sesión no encontrada")

    # Buscar intento asociado
    result = await db.execute(
        select(ExamAttempt).where(ExamAttempt.session_id == session.id)
    )
    intento = result.scalar_one_or_none()

    if not intento:
        raise HTTPException(404, "Intento no encontrado")

    # Evitar overwrite
    if intento.display_name:
        raise HTTPException(400, "Nombre ya asignado")

    intento.display_name = data.nombre[:50]
    await db.commit()

    return {"ok": True}