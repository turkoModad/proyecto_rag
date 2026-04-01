from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.database import get_db
from app.auth.access_log_service import get_suspicious_ips, get_endpoint_hits
from app.administracion.security.admin_security import require_admin
from app.middleware.security_middleware import rate_limiter
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func
from app.auth.access_log_service import get_suspicious_ips, get_endpoint_hits, AccessLog


router = APIRouter(
    prefix="/security",
    tags=["Security"],
    dependencies=[Depends(require_admin)]  
)


@router.get("/suspicious-ips")
async def suspicious_ips(
    minutes: int = 5,
    min_requests: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint para administradores: lista IPs con actividad sospechosa
    """
    ips = await get_suspicious_ips(db, min_requests, minutes)
    return {
        "period_minutes": minutes,
        "min_requests": min_requests,
        "suspicious_ips": ips
    }


@router.get("/top-endpoints")
async def top_endpoints(
    minutes: int = 5,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint para administradores: endpoints más solicitados
    """
    endpoints = await get_endpoint_hits(db, minutes)
    return {
        "period_minutes": minutes,
        "top_endpoints": endpoints
    }


@router.get("/blocked-ips")
async def get_blocked_ips():
    """
    Lista IPs bloqueadas actualmente
    """
    now = datetime.now(timezone.utc)
    blocked = []
    
    for ip, (blocked_until, reason) in rate_limiter.blocked_ips.items():
        if blocked_until > now:
            remaining = (blocked_until - now).seconds // 60
            blocked.append({
                "ip": ip,
                "blocked_until": blocked_until.isoformat(),
                "remaining_minutes": remaining,
                "reason": reason
            })
    
    return {
        "total_blocked": len(blocked),
        "blocked_ips": blocked
    }


@router.delete("/unblock-ip/{ip}")
async def unblock_ip(ip: str):
    """
    Desbloquea una IP manualmente
    """
    if ip in rate_limiter.blocked_ips:
        del rate_limiter.blocked_ips[ip]
        return {"message": f"IP {ip} desbloqueada"}
    return {"message": f"IP {ip} no estaba bloqueada"}


@router.get("/analytics/countries")
async def analytics_by_country(
    minutes: int = 60,
    db: AsyncSession = Depends(get_db)
):
    """
    Estadísticas de requests por país
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    result = await db.execute(
        select(
            AccessLog.cf_country,
            func.count().label('requests'),
            func.avg(AccessLog.response_time_ms).label('avg_response_time')
        )
        .where(
            AccessLog.timestamp >= since,
            AccessLog.cf_country.isnot(None)
        )
        .group_by(AccessLog.cf_country)
        .order_by(func.count().desc())
    )
    
    rows = result.all()
    return {
        "period_minutes": minutes,
        "countries": [
            {
                "country": row[0],
                "requests": row[1],
                "avg_response_time_ms": round(row[2], 2) if row[2] else 0
            }
            for row in rows
        ]
    }


@router.get("/analytics/errors")
async def error_analytics(
    minutes: int = 60,
    db: AsyncSession = Depends(get_db)
):
    """
    Análisis de errores por endpoint
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    result = await db.execute(
        select(
            AccessLog.endpoint,
            AccessLog.status_code,
            func.count().label('occurrences')
        )
        .where(
            AccessLog.timestamp >= since,
            AccessLog.status_code >= 400
        )
        .group_by(AccessLog.endpoint, AccessLog.status_code)
        .order_by(func.count().desc())
        .limit(20)
    )
    
    rows = result.all()
    return {
        "period_minutes": minutes,
        "errors": [
            {
                "endpoint": row[0],
                "status_code": row[1],
                "occurrences": row[2]
            }
            for row in rows
        ]
    }


@router.get("/analytics/rate-limiting")
async def rate_limiting_analytics(
    minutes: int = 60,
    db: AsyncSession = Depends(get_db)
):
    """
    IPs que más cerca estuvieron del rate limit
    Usa el nuevo índice compuesto ip_timestamp
    """
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    
    result = await db.execute(
        select(
            AccessLog.ip_address,
            func.count().label('total_requests'),
            func.count(func.distinct(func.date_trunc('minute', AccessLog.timestamp))).label('active_minutes')
        )
        .where(AccessLog.timestamp >= since)
        .group_by(AccessLog.ip_address)
        .having(func.count() > 30)  
        .order_by(func.count().desc())
        .limit(20)
    )
    
    rows = result.all()
    return {
        "period_minutes": minutes,
        "top_ips": [
            {
                "ip": row[0],
                "total_requests": row[1],
                "active_minutes": row[2],
                "avg_requests_per_minute": round(row[1] / max(row[2], 1), 2)
            }
            for row in rows
        ]
    }