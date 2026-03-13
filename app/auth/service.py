import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import User, QueryLog, OTPLog
from app.auth.security import hash_password, verify_password
from app.core.security import encrypt_value, hash_email

logger = logging.getLogger("AuthService")


# ----------------------------
# USUARIOS
# ----------------------------
async def get_user_by_email(db: AsyncSession, email: str):
    """Busca un usuario usando hash determinístico de email"""
    email_hashed = hash_email(email)
    result = await db.execute(select(User).where(User.email_hash == email_hashed))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str):
    """
    Crea un usuario, devuelve objeto y hash determinístico de email usado para búsquedas/OTP
    """
    encrypted_email = encrypt_value(email)   # email cifrado para recuperación
    email_hashed = hash_email(email)         # hash determinístico para búsquedas
    hashed_password = hash_password(password)
    
    new_user = User(
        email=encrypted_email,
        email_hash=email_hashed,
        password_hash=hashed_password,
        is_verified=False,
        is_blocked=False,
        otp_attempts=0
    )
    db.add(new_user)
    await db.flush()  
    return new_user, email_hashed


async def authenticate_user(db: AsyncSession, email: str, password: str):
    """Autentica usuario comparando contraseña y hash determinístico"""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):  
        return None
    return user


# ----------------------------
# LOGS DE CONSULTAS
# ----------------------------
async def log_query(
    db: AsyncSession,
    user_id: str | None,
    ip_address: str,
    user_agent: str | None,
    question: str,
    response: str,
    decision: str,
    tokens_generated: int | None,
    response_time_ms: int | None,
    endpoint: str,
    model_used: str | None = None,
    temperature: float | None = None,
    top_k_retrieved: int | None = None,
    qa_cache_score: float | None = None,
    retrieval_score: float | None = None,
    grounding_score: float | None = None
):
    """Registra una consulta en la base de datos"""
    query_log = QueryLog(
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        question=question,
        response=response,
        decision=decision,
        tokens_generated=tokens_generated,
        response_time_ms=response_time_ms,
        endpoint=endpoint,
        model_used=model_used,
        temperature=temperature,
        top_k_retrieved=top_k_retrieved,
        qa_cache_score=qa_cache_score,
        retrieval_score=retrieval_score,
        grounding_score=grounding_score
    )
    db.add(query_log)
    await db.commit()
    return query_log


async def count_user_queries(db: AsyncSession, user_id: str) -> int:
    """Cuenta consultas de un usuario (para límites)"""
    result = await db.execute(
        select(func.count()).select_from(QueryLog).where(
            (QueryLog.user_id == user_id) &
            (QueryLog.decision != "pending")
        )
    )
    return result.scalar() or 0


async def count_anonymous_queries(db: AsyncSession, ip_address: str, endpoint: str = "/ask") -> int:
    """Cuenta consultas anónimas desde una IP"""
    result = await db.execute(
        select(func.count()).select_from(QueryLog).where(
            (QueryLog.user_id == None) &
            (QueryLog.ip_address == ip_address) &
            (QueryLog.endpoint == endpoint) &
            (QueryLog.decision != "pending")
        )
    )
    return result.scalar() or 0


# ----------------------------
# LOGS DE OTP
# ----------------------------
async def count_otp_ip_today(db: AsyncSession, ip_address: str):
    """Cuenta OTPs enviados desde una IP hoy"""
    result = await db.execute(
        select(func.count()).select_from(OTPLog).where(
            OTPLog.ip_address == ip_address,
            func.date(OTPLog.created_at) == func.current_date()
        )
    )
    return result.scalar() or 0


async def log_otp(db: AsyncSession, email: str, ip_address: str, purpose: str = None):
    """
    Registra un OTP enviado.
    Usa hash determinístico de email para búsquedas y limitación de envíos.
    """
    # Si ya viene hash (por ejemplo desde create_user) lo usamos tal cual
    if '@' in email:
        email_hashed = hash_email(email)
    else:
        email_hashed = email

    log = OTPLog(
        email=email_hashed,
        ip_address=ip_address,
        purpose=purpose
    )
    db.add(log)
    await db.commit()
    return log


async def get_user_by_token(db: AsyncSession, token: str):
    """
    Busca un usuario por OTP token.
    Retorna None si no existe.
    """
    query = select(User).where(User.otp_token == token)
    result = await db.execute(query)
    user = result.scalars().first()
    return user