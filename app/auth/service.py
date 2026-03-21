import logging
import re
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import User, QueryLog, OTPLog, RefreshToken
from app.auth.security import hash_password, verify_password
from app.core.security import encrypt_value, hash_email
from datetime import datetime, timezone
from fastapi import Request, Response


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


async def get_user_by_id(db: AsyncSession, user_id: str):
    try:
        result = await db.execute(
            select(User).where(User.id == user_id) 
        )
        user = result.scalar_one_or_none()
        return user
    except Exception as e:
        logger.error(f"Error al buscar usuario por ID {user_id}: {e}")
        return None
    

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Valida que la contraseña tenga:
    - Mínimo 8 caracteres
    - Al menos una letra mayúscula
    - Al menos un número
    - Al menos un carácter especial
    """
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres"
    if not re.search(r"[A-Z]", password):
        return False, "La contraseña debe contener al menos una letra mayúscula"
    if not re.search(r"\d", password):
        return False, "La contraseña debe contener al menos un número"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "La contraseña debe contener al menos un carácter especial"
    return True, ""


async def create_user(db: AsyncSession, email: str, password: str):
    """
    Crea un usuario, devuelve objeto y hash determinístico de email usado para búsquedas/OTP
    """
    is_valid, msg = validate_password_strength(password)
    if not is_valid:
        raise ValueError(msg)  

    encrypted_email = encrypt_value(email)   
    email_hashed = hash_email(email)         
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


async def create_refresh_token_record(db: AsyncSession, user_id: str, jti: str, expires_at: datetime):
    """Guarda un refresh token en la BD"""
    token_record = RefreshToken(
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
        revoked=False  
    )
    db.add(token_record)
    await db.commit()
    await db.refresh(token_record)
    return token_record


async def get_refresh_token_by_jti(db: AsyncSession, jti: str):
    """Obtiene el registro de refresh token por jti (sin filtrar por revocado)"""
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, jti: str):
    """Marca un refresh token como revocado"""
    token_record = await get_refresh_token_by_jti(db, jti)
    if token_record and not token_record.revoked:
        token_record.revoked = True
        await db.commit()
        return True
    return False


def utc_now():
    return datetime.now(timezone.utc)

def get_real_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("CF-Connecting-IP") or request.client.host or "unknown"


def clear_auth_cookies(response: Response):
    cookie_config = {
        "httponly": True,
        "secure": True,
        "samesite": "Lax",
        "path": "/"
    }
    response.delete_cookie("access_token", **cookie_config)
    response.delete_cookie("refresh_token", **cookie_config)


async def revoke_all_user_refresh_tokens(db: AsyncSession, user_id: str):
    """Revoca todos los refresh tokens activos de un usuario"""
    stmt = update(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).values(revoked=True)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount