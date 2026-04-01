from fastapi import APIRouter, HTTPException, Depends, Request
import json, random, secrets, hmac, hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc, update

from app.auth.database import get_db
from app.auth.models import ExamSession, ExamAttempt, ExamLog
from app.auth.dependencies import get_current_user_db, get_or_create_anon_id
from app.core.config import SECRET_EXAMENES, ARCHIVO_PREGUNTAS


router = APIRouter(tags=["examen"])

DURACION_EXAMEN = 600
MAX_ATTEMPTS_PER_MINUTE = 5

NIVELES = {
    "aprendiz": 20,
    "veterano": 40,
    "leyenda": 60
}


def cargar_preguntas():
    preguntas = []
    with open(ARCHIVO_PREGUNTAS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                preguntas.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Error al saltar línea corrupta: {line[:50]}...")
                continue
    return preguntas


PREGUNTAS_DB = cargar_preguntas()


class StartRequest(BaseModel):
    nivel: str
    fingerprint: str


class AnswerRequest(BaseModel):
    token: str
    question_id: int
    seleccion: int
    firma: str
    tiempo: float
    ts: int


class FinishRequest(BaseModel):
    token: str
    nombre: Optional[str] = Field(None, max_length=10)


class SaveNameRequest(BaseModel):
    token: str
    nombre: str = Field(..., max_length=10)


def firmar(qid, ts):
    msg = f"{qid}:{ts}"
    return hmac.new(SECRET_EXAMENES.encode(), msg.encode(), hashlib.sha256).hexdigest()


def verificar_firma(firma, qid, ts):
    return hmac.compare_digest(firma, firmar(qid, ts))


def get_medalla(score, total):
    r = score / total
    if r >= 0.9: return "🥇"
    if r >= 0.75: return "🥈"
    if r >= 0.6: return "🥉"
    return ""


async def log(db, session_id, ip, ua, action, extra=None):
    try:
        db.add(ExamLog(
            session_id=session_id,
            ip_address=ip,
            user_agent=ua,
            action=action,
            details=json.dumps(extra, ensure_ascii=False) if extra else None  
        ))
        await db.commit()
    except:
        pass


async def rate_limit(db, ip):
    limite = datetime.now(timezone.utc) - timedelta(minutes=1)
    result = await db.execute(
        select(ExamSession).where(
            ExamSession.ip_address == ip,
            ExamSession.start_time >= limite
        )
    )
    if len(result.scalars().all()) >= MAX_ATTEMPTS_PER_MINUTE:
        raise HTTPException(429, "Demasiados intentos")


def build_question(session, index):
    question_ids = json.loads(session.questions_data)
    if index >= len(question_ids):
        return {"finished": True}

    qid = question_ids[index]
    p = next((x for x in PREGUNTAS_DB if x["id"] == qid), None)
    if not p:
        return {"finished": True}

    shuffled_map = json.loads(session.shuffled_data) if session.shuffled_data else {}
    shuffle_info = shuffled_map.get(str(qid))  
    if not shuffle_info:
        opciones = p["respuestas"]
    else:
        opciones = shuffle_info["shuffled"]

    ts = int(datetime.now().timestamp())
    firma = firmar(p["id"], ts)

    return {
        "token": session.token,
        "question_id": p["id"],
        "pregunta": p["pregunta"],
        "opciones": opciones,
        "index": index,
        "ts": ts,
        "firma": firma
    }


@router.post("/examen/start")
async def start(
    req: StartRequest,
    request: Request,
    anon_id: str = Depends(get_or_create_anon_id),
    user = Depends(get_current_user_db),
    db: AsyncSession = Depends(get_db)
):
    ip = request.client.host
    ua = request.headers.get("user-agent","")

    await rate_limit(db, ip)

    if req.nivel not in NIVELES:
        raise HTTPException(400, "Nivel inválido")

    try:
        await db.execute(
            update(ExamSession)
            .where(
                ExamSession.anon_id == anon_id,
                ExamSession.evaluated == False,
            )
            .values(evaluated=True)
        )

        await db.flush()

        cantidad = min(NIVELES[req.nivel], len(PREGUNTAS_DB))
        preguntas = random.sample(PREGUNTAS_DB, cantidad)

        shuffled_map = {}
        for p in preguntas:
            shuffled_answers = p["respuestas"].copy()
            random.shuffle(shuffled_answers)

            if p["correcta"] not in shuffled_answers:
                raise HTTPException(500, f"Error en dataset: {p['pregunta']}")

            correct_index = shuffled_answers.index(p["correcta"])

            shuffled_map[str(p["id"])] = {
                "shuffled": shuffled_answers,
                "correct_index": correct_index
            }

        question_ids = [p["id"] for p in preguntas]
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)

        session = ExamSession(
            token=token,
            user_id=user.id if user else None,
            anon_id=anon_id,
            ip_address=ip,
            user_agent=ua,
            fingerprint=req.fingerprint,
            nivel=req.nivel,
            questions_data=json.dumps(question_ids, ensure_ascii=False),
            answers_data=json.dumps([], ensure_ascii=False),
            current_index=0,
            total_questions=cantidad,
            start_time=now,
            expires_at=now + timedelta(seconds=DURACION_EXAMEN),
            evaluated=False,
            shuffled_data=json.dumps(shuffled_map, ensure_ascii=False)
        )

        db.add(session)

        await db.commit()
        await db.refresh(session)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Reintentá (colisión de sesión)")

    await log(db, session.id, ip, ua, "start")
    return build_question(session, 0)


@router.post("/examen/answer")
async def answer(req: AnswerRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.client.host
    ua = request.headers.get("user-agent","")

    # Traer sesión
    result = await db.execute(select(ExamSession).where(ExamSession.token == req.token))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(400, "Sesión inválida")
    if session.evaluated:
        raise HTTPException(400, "Examen ya finalizado")
    if datetime.now(timezone.utc) > session.expires_at:
        raise HTTPException(400, "Examen expirado")
    if session.ip_address != ip:
        raise HTTPException(403, "IP sospechosa")

    question_ids = json.loads(session.questions_data)
    if session.current_index >= len(question_ids):
        raise HTTPException(400, "Examen terminado")

    qid_actual = question_ids[session.current_index]
    if qid_actual != req.question_id:
        raise HTTPException(400, "Orden inválido")
    if not verificar_firma(req.firma, req.question_id, req.ts):
        raise HTTPException(400, "Firma inválida")

    shuffled_map = json.loads(session.shuffled_data) if session.shuffled_data else {}
    shuffle_info = shuffled_map.get(str(req.question_id))

    es_correcta = False
    if shuffle_info:
        correct_index = shuffle_info["correct_index"]
        es_correcta = (req.seleccion == correct_index)
    else:
        p = next((x for x in PREGUNTAS_DB if x["id"] == req.question_id), None)
        if p and 0 <= req.seleccion < len(p["respuestas"]):
            es_correcta = p["respuestas"][req.seleccion] == p["correcta"]

    print(f"[DEBUG] Pregunta ID: {req.question_id}, Selección: {req.seleccion}, Correcta: {es_correcta}")

    respuestas = json.loads(session.answers_data)
    respuestas.append({
        "id": req.question_id,
        "seleccion": req.seleccion,
        "tiempo": req.tiempo,
        "correcta": es_correcta
    })
    session.answers_data = json.dumps(respuestas, ensure_ascii=False)
    session.current_index += 1
    await db.commit()

    await log(db, session.id, ip, ua, "answer", {"q": req.question_id, "seleccion": req.seleccion, "correcta": es_correcta})

    return build_question(session, session.current_index)



@router.post("/examen/finish")
async def finish(req: FinishRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.client.host
    ua = request.headers.get("user-agent", "")

    result = await db.execute(select(ExamSession).where(ExamSession.token == req.token))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(400, "Sesión inválida")
    if session.evaluated:
        raise HTTPException(400, "Examen ya evaluado")

    question_ids = json.loads(session.questions_data)
    respuestas = json.loads(session.answers_data)

    correctas = sum(1 for r in respuestas if r.get("correcta", False))
    print(f"[DEBUG] Evaluando examen {session.id} con {len(respuestas)} respuestas. Correctas: {correctas}")

    tiempos = [r.get("tiempo", 0) for r in respuestas]
    duracion = (datetime.now(timezone.utc) - session.start_time).total_seconds()
    avg = sum(tiempos)/len(tiempos) if tiempos else 0
    var = sum((t-avg)**2 for t in tiempos)/len(tiempos) if tiempos else 0

    fraud = 0
    if avg < 1.2: fraud += 2
    if var < 0.5: fraud += 2
    if correctas == len(question_ids) and duracion < 60: fraud += 3

    is_valid = fraud < 4

    intento = ExamAttempt(
        user_id=session.user_id,
        anon_id=session.anon_id,
        display_name=req.nombre[:50] if req.nombre else None,
        ip_address=ip,
        score=correctas,
        total=len(question_ids),
        duration_seconds=int(duracion),
        avg_time=avg,
        variance_time=var,
        fraud_score=fraud,
        completed=True,
        is_valid=is_valid,
        session_id=session.id
    )

    db.add(intento)
    session.evaluated = True
    await db.commit()
    await db.refresh(intento)

    await log(db, session.id, ip, ua, "finish", {"score": correctas, "valido": is_valid, "duracion": duracion, "fraud": fraud, "respuestas": respuestas})

    print(f"[DEBUG] Resultado final: {correctas}/{len(question_ids)}, válido: {is_valid}, duración: {duracion}s")

    return {
        "resultado": correctas,
        "total": len(question_ids),
        "duracion": int(duracion),
        "medalla": get_medalla(correctas, len(question_ids)),
        "valido": is_valid,
        "attempt_id": intento.id
    }


@router.post("/examen/save_name")
async def save_name(req: SaveNameRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ExamAttempt).where(ExamAttempt.id == req.token)
    )
    intento = result.scalar_one_or_none()
    if not intento:
        raise HTTPException(400, "Intento no encontrado")
    intento.display_name = req.nombre[:50]
    await db.commit()
    return {"ok": True}


@router.get("/examen/top10/{nivel}")
async def top10(nivel: str, db: AsyncSession = Depends(get_db)):
    if nivel not in NIVELES:
        raise HTTPException(400, "Nivel inválido")

    total = NIVELES[nivel]
    result = await db.execute(
        select(ExamAttempt)
        .where(
            ExamAttempt.completed == True,
            ExamAttempt.is_valid == True,
            ExamAttempt.total == total,
            ExamAttempt.score >= (ExamAttempt.total * 0.7)
        )
        .order_by(desc(ExamAttempt.score), asc(ExamAttempt.duration_seconds))
        .limit(10)
    )

    return [{
        "nombre": r.display_name or "Anónimo",
        "score": r.score,
        "total": r.total,
        "duracion": r.duration_seconds,
        "medalla": get_medalla(r.score, r.total)
    } for r in result.scalars().all()]