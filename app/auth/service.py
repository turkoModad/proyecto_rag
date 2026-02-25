from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.models import User, QueryLog  
from app.auth.security import hash_password, verify_password
import logging


logger = logging.getLogger("AuthService")


async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str):
    user = User(
        email=email,
        password_hash=hash_password(password)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str):
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


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
    """Cuenta el total de consultas de un usuario (para límites) usando QueryLog"""
    result = await db.execute(
        select(func.count()).select_from(QueryLog).where(
            (QueryLog.user_id == user_id) &
            (QueryLog.decision != "pending") 
        )
    )
    return result.scalar() or 0


async def count_anonymous_queries(db: AsyncSession, ip_address: str, endpoint: str = "/ask") -> int:
    """Cuenta las consultas anónimas desde una IP"""
    result = await db.execute(
        select(func.count()).where(
            (QueryLog.user_id == None) &
            (QueryLog.ip_address == ip_address) &
            (QueryLog.endpoint == endpoint) &
            (QueryLog.decision != "pending")
        )
    )
    return result.scalar() or 0