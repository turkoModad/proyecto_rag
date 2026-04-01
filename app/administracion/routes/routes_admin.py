# app/administracion/routes_admin.py

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from app.administracion.security.admin_security import require_admin, require_admin_with_refresh
from app.auth.database import get_db
from app.auth.models import User, AccessLog, Visit, QueryLog, Review, ExamAttempt, ContactMessage
from app.core.config import VALID_ROLES
from fastapi.responses import HTMLResponse
from pathlib import Path
from app.auth.jwt_handler import create_access_token, create_refresh_token
from datetime import datetime, timezone


refresh_router = APIRouter(prefix="/admin")


@refresh_router.post("/refresh")
async def refresh_admin_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_with_refresh)  
):
    """
    Endpoint para renovar tokens admin.
    Este es el ÚNICO endpoint que acepta refresh token.
    Úsalo cuando el access token haya expirado.
    """
    new_access_token = create_access_token(str(admin_user.id), admin_user.role)
    new_refresh_token, jti = create_refresh_token(str(admin_user.id))
    
    hostname = request.url.hostname or ""
    secure_cookie = False if "localhost" in hostname or "127.0.0.1" in hostname else True
    
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=15 * 60  # 15 minutos
    )
    
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        max_age=24 * 60 * 60  # 1 día
    )
    
    return {
        "message": "Sesión renovada exitosamente",
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "expires_in": 900,  
        "user": {
            "id": admin_user.id,
            "email": admin_user.email,
            "role": admin_user.role
        }
    }


router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_admin)]  
)


@router.get("/", response_class=HTMLResponse)
async def admin_panel(
    request: Request, 
    user = Depends(require_admin) 
):
    html_path = Path("frontend/administracion.html")
    return html_path.read_text(encoding="utf-8")



@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [dict(
        id=str(u.id),
        email=u.email,
        role=u.role,
        is_active=u.is_active,
        is_blocked=u.is_blocked,
        created_at=str(u.created_at)
    ) for u in users]



@router.post("/users/block")
async def block_user(
    user_id: str, 
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    stmt = update(User).where(User.id == user_id).values(is_blocked=True)
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "message": f"Usuario {user_id} bloqueado por {admin_user.email}"}



@router.post("/users/unblock")
async def unblock_user(
    user_id: str, 
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    stmt = update(User).where(User.id == user_id).values(is_blocked=False)
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "message": f"Usuario {user_id} desbloqueado por {admin_user.email}"}



@router.post("/users/admin")
async def make_admin(
    user_id: str, 
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    stmt = update(User).where(User.id == user_id).values(role="admin")
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "message": f"Usuario {user_id} ahora es admin por {admin_user.email}"}



@router.post("/users/delete")
async def delete_user(
    user_id: str, 
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    stmt = delete(User).where(User.id == user_id)
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok", "message": f"Usuario {user_id} eliminado por {admin_user.email}"}



@router.post("/users/{user_id}/role")
async def change_role(
    user_id: str,
    role: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido")

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    try:
        user.role = role
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error actualizando rol")

    return {"status": "ok", "new_role": role, "changed_by": admin_user.email}



@router.get("/ips")
async def get_ips(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(
        select(
            AccessLog.ip_address,
            func.count().label("requests")
        )
        .group_by(AccessLog.ip_address)
        .order_by(func.count().desc())
        .limit(100)
    )

    return [{"ip": r[0], "requests": r[1]} for r in result.all()]



@router.get("/ips/detail")
async def get_ips_detail(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(
        select(
            AccessLog.ip_address,
            func.count().label("requests"),
            func.count(func.distinct(AccessLog.user_id)).label("users")
        )
        .group_by(AccessLog.ip_address)
        .order_by(func.count().desc())
        .limit(100)
    )

    return [
        {
            "ip": r[0],
            "requests": r[1],
            "registered_users": r[2] > 0
        }
        for r in result.all()
    ]



@router.get("/ips/users")
async def get_ips_users(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(
        select(
            AccessLog.ip_address,
            AccessLog.user_id,
            func.count().label("requests")
        )
        .where(AccessLog.user_id.is_not(None))
        .group_by(AccessLog.ip_address, AccessLog.user_id)
        .order_by(func.count().desc())
    )

    return [
        {
            "ip": r[0],
            "user_id": str(r[1]),
            "requests": r[2]
        }
        for r in result.all()
    ]



@router.get("/top-endpoints")
async def top_endpoints(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(
        select(
            AccessLog.endpoint,
            func.count().label("hits")
        )
        .group_by(AccessLog.endpoint)
        .order_by(func.count().desc())
        .limit(20)
    )

    return [{"endpoint": r[0], "hits": r[1]} for r in result.all()]



@router.get("/visits")
async def visits(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(
        select(Visit.ip_address, func.count(Visit.id).label("visits"))
        .group_by(Visit.ip_address)
        .order_by(func.count(Visit.id).desc())
    )
    rows = result.all()
    return [{"ip": r.ip_address, "visits": r.visits} for r in rows]


@router.post("/ips/block")
async def block_ip(
    ip: str,
    admin_user: User = Depends(require_admin)  
):
    return {"status": "ok", "message": f"IP {ip} bloqueada por {admin_user.email}"}



@router.get("/qa/logs")
async def qa_logs(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(select(QueryLog))
    logs = result.scalars().all()
    return [dict(
        id=str(l.id),
        user_id=str(l.user_id) if l.user_id else None,
        ip_address=l.ip_address,
        question=l.question,
        rewritten_query=l.rewritten_query,
        response=l.response,
        decision=l.decision,
        timestamp=str(l.timestamp)
    ) for l in logs]



@router.get("/qa/out_of_domain")
async def qa_out_of_domain(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(select(QueryLog).where(QueryLog.decision=="out_of_domain"))
    logs = result.scalars().all()
    return [dict(
        id=str(l.id),
        question=l.question,
        rewritten_query=l.rewritten_query,
        response=l.response
    ) for l in logs]



@router.get("/reviews")
async def reviews(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(select(Review))
    rows = result.scalars().all()
    return [{"id": r.id, "user_id": str(r.user_id) if r.user_id else None, "ip": r.ip_address, "rating": r.rating, "comment": r.comment, "created_at": str(r.created_at)} for r in rows]



@router.get("/exam_attempts")
async def exam_attempts(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(select(ExamAttempt))
    attempts = result.scalars().all()
    return [{"id": a.id, "user_id": str(a.user_id) if a.user_id else None, "ip": a.ip_address, "score": a.score, "total": a.total, "completed": a.completed, "created_at": str(a.created_at)} for a in attempts]



@router.get("/messages")
async def contact_messages(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin)  
):
    result = await db.execute(select(ContactMessage))
    messages = result.scalars().all()
    return [{"id": m.id, "email": m.email, "message": m.message, "ip": m.ip_address, "created_at": str(m.created_at)} for m in messages]