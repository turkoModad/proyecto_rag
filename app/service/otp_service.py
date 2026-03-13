from sqlalchemy import select, func
from datetime import datetime, timezone
from fastapi import HTTPException
from app.auth.models import OTPLog
from app.core.security import hash_email
from app.core.config import MAX_OTP_PER_IP


async def check_otp_rate_limit(db, ip: str):
    """Verifica cuántos OTP se generaron desde una IP hoy"""
    today = datetime.now(timezone.utc).date()

    query = (
        select(func.count())
        .select_from(OTPLog)
        .where(
            OTPLog.ip_address == ip,
            func.date(OTPLog.created_at) == today
        )
    )

    result = await db.execute(query)
    count = result.scalar() or 0

    if count >= MAX_OTP_PER_IP:
        raise HTTPException(
            status_code=429,
            detail="Límite diario de OTP alcanzado"
        )


async def log_otp(db, email: str, ip: str, purpose: str = None):
    """
    Guarda un registro de OTP en la DB usando hash determinístico del email
    """
    email_hash = hash_email(email)

    log = OTPLog(
        ip_address=ip,
        email=email_hash,
        purpose=purpose
    )

    db.add(log)
    await db.commit()
    return log