from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta, timezone
from app.auth.models import AccessLog
import logging
from typing import Optional


logger = logging.getLogger("AccessLogService")


def sanitize_string(value: Optional[str], max_length: int = 2000) -> Optional[str]:
    if not value:
        return None
    return value[:max_length]


async def log_access(
    db: AsyncSession,
    ip_address: str,
    method: str,
    endpoint: str,
    status_code: int,
    user_agent: Optional[str] = None,
    referer: Optional[str] = None,
    user_id: Optional[str] = None,
    response_time_ms: Optional[int] = None,
    cf_country: Optional[str] = None
) -> Optional[AccessLog]:
    """
    Registra un acceso a cualquier endpoint.
    NO hace commit ni rollback.
    """
    try:
        log_entry = AccessLog(
            ip_address=ip_address,
            user_id=user_id,
            method=method[:10],
            endpoint=sanitize_string(endpoint, 500),
            status_code=status_code,
            user_agent=sanitize_string(user_agent, 2000),
            referer=sanitize_string(referer, 2000),
            response_time_ms=response_time_ms,
            cf_country=cf_country[:2] if cf_country else None
        )
        
        db.add(log_entry)

        return log_entry
        
    except Exception as e:
        logger.error(f"Error creando access log (sin commit): {e}")
        return None


async def count_requests_from_ip(
    db: AsyncSession,
    ip_address: str,
    minutes: int = 5
) -> int:
    """
    Cuenta cuántas peticiones ha hecho una IP en los últimos X minutos
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    result = await db.execute(
        select(func.count()).select_from(AccessLog).where(
            and_(
                AccessLog.ip_address == ip_address,
                AccessLog.timestamp >= since
            )
        )
    )
    return result.scalar() or 0


async def get_suspicious_ips(
    db: AsyncSession,
    min_requests: int = 100,
    minutes: int = 5
) -> list:
    """
    Detecta IPs con actividad sospechosa (muchas peticiones en poco tiempo)
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    result = await db.execute(
        select(
            AccessLog.ip_address,
            func.count().label('request_count')
        )
        .where(AccessLog.timestamp >= since)
        .group_by(AccessLog.ip_address)
        .having(func.count() >= min_requests)
        .order_by(func.count().desc())
    )
    
    rows = result.all()
    return [{"ip": row[0], "count": row[1]} for row in rows]


async def get_endpoint_hits(
    db: AsyncSession,
    minutes: int = 5
) -> list:
    """
    Obtiene los endpoints más solicitados
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    result = await db.execute(
        select(
            AccessLog.endpoint,
            func.count().label('hits')
        )
        .where(AccessLog.timestamp >= since)
        .group_by(AccessLog.endpoint)
        .order_by(func.count().desc())
        .limit(20)
    )
    
    rows = result.all()
    return [{"endpoint": row[0], "hits": row[1]} for row in rows]