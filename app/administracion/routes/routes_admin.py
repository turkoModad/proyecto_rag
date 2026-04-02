from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.administracion.security.admin_security import (
    require_admin,
    require_admin_with_refresh,
    require_admin_with_session_password,
    create_admin_session
)

from app.auth.database import get_db
from app.auth.models import User, AccessLog, Visit, QueryLog, Review, ExamAttempt, ContactMessage, AdminSession
from app.core.config import VALID_ROLES
from app.auth.jwt_handler import create_access_token, create_refresh_token
from app.core.security import decrypt_value
from email_service.email_sender import enviar_email
import logging
from app.core.security import decrypt_value  
from app.core.security import hash_session_password, generate_session_salt
from app.core.config import SESSION_PASSWORD_EXPIRE_MINUTES

logger = logging.getLogger("routes_admin")
logger.setLevel(logging.INFO)


auth_router = APIRouter(prefix="/admin")


@auth_router.post("/refresh")
async def refresh_admin_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_with_refresh)
):
    new_access_token = create_access_token(str(admin_user.id), admin_user.role)
    new_refresh_token, _ = create_refresh_token(str(admin_user.id))

    hostname = request.url.hostname or ""
    secure_cookie = False if "localhost" in hostname or "127.0.0.1" in hostname else True

    response.set_cookie("access_token", new_access_token, httponly=True, secure=secure_cookie, samesite="Lax", max_age=900)
    response.set_cookie("refresh_token", new_refresh_token, httponly=True, secure=secure_cookie, samesite="Lax", max_age=86400)

    return {"message": "Sesión renovada"}



@auth_router.post("/request-session-password")
async def request_session_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_admin_with_refresh)
):
    """Envía contraseña de sesión al email del admin"""
    
    try:
        email_plain = decrypt_value(admin_user.email)
    except Exception as e:
        logger.error(f"Error descifrando email del admin {admin_user.id}: {e}")
        raise HTTPException(
            status_code=400, 
            detail="Error al procesar el email del administrador"
        )
    
    if not email_plain or "@" not in email_plain:
        raise HTTPException(
            status_code=400, 
            detail="El usuario admin no tiene un email válido configurado"
        )
    
    session_password, session_id = await create_admin_session(
        user_id=admin_user.id,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
        db=db
    )

    await db.commit()

    html = f"""
    <h2>🔐 Acceso Admin</h2>
    <p>Tu contraseña de sesión es:</p>
    <h1 style="font-size: 32px; letter-spacing: 4px;">{session_password}</h1>
    <p>Expira en 30 minutos</p>
    <p>Ingresa esta contraseña en el panel de administración.</p>
    """

    enviado = enviar_email(email_plain, "🔐 Contraseña de sesión - Admin", html)
    
    if not enviado:
        raise HTTPException(
            status_code=500,
            detail="No se pudo enviar el email. Contacte al administrador."
        )

    return {"message": "Contraseña enviada al email"}




public_router = APIRouter(prefix="/admin")


@public_router.get("/", response_class=HTMLResponse)
async def admin_login_page(
    user: User = Depends(require_admin)  
):
    """Muestra la página para ingresar la contraseña de sesión"""
    html_path = Path("frontend/admin_login.html")
    return html_path.read_text(encoding="utf-8")



@public_router.post("/validate-session-password")
async def validate_session_password(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin) 
):
    from app.administracion.security.admin_security import verify_admin_session
    from app.auth.models import AdminSession
    from sqlalchemy import and_
    from datetime import datetime, timezone
    
    try:
        body = await request.json()
        session_password = body.get("session_password")
    except Exception as e:
        raise HTTPException(status_code=400, detail="session_password requerido en body")
    
    if not session_password:
        raise HTTPException(status_code=400, detail="session_password no proporcionado")
    
    is_valid, error_msg = await verify_admin_session(user.id, session_password, db)
    
    if not is_valid:
        raise HTTPException(status_code=401, detail=error_msg or "Contraseña inválida")
    
    now = datetime.now(timezone.utc)
    
    result = await db.execute(
        select(AdminSession).where(
            and_(
                AdminSession.user_id == user.id,
                AdminSession.is_active == True,
                AdminSession.session_password_expires_at > now
            )
        ).order_by(AdminSession.created_at.desc()).limit(1)
    )
    admin_session = result.scalar_one_or_none()
    
    if not admin_session:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    
    response.delete_cookie("session_password", path="/")
    response.delete_cookie("session_password_hash", path="/")
    response.delete_cookie("session_password_salt", path="/")
    
    hostname = request.url.hostname or ""
    secure_cookie = False if "localhost" in hostname or "127.0.0.1" in hostname else True
    
    response.set_cookie(
        key="session_password_hash",
        value=admin_session.session_password_hash,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        path="/",
        max_age=SESSION_PASSWORD_EXPIRE_MINUTES * 60
    )
    
    response.set_cookie(
        key="session_password_salt",
        value=admin_session.session_password_salt,
        httponly=True,
        secure=secure_cookie,
        samesite="Lax",
        path="/",
        max_age=SESSION_PASSWORD_EXPIRE_MINUTES * 60
    )
    
    return {"valid": True, "message": "Contraseña válida"}



protected_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_admin_with_session_password)]
)



@protected_router.get("/panel", response_class=HTMLResponse)
async def admin_panel(
    session_password: str = Query(None),
    user: User = Depends(require_admin_with_session_password)
):
    """Panel real de administración"""
    html_path = Path("frontend/administracion.html")
    return html_path.read_text(encoding="utf-8")



@protected_router.get("/verify-session")
async def verify_session(
    session_password: str = Query(None),
    user: User = Depends(require_admin_with_session_password)
):
    """Verificar que la sesión admin es válida"""
    return {"valid": True}



@protected_router.post("/logout-session")
async def logout_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    from app.auth.models import AdminSession
    from app.auth.dependencies import get_current_user_with_full_security
    from sqlalchemy import update, and_
    
    # Obtener usuario actual desde la cookie (sin validación extra)
    user = await get_current_user_with_full_security(request, db, allow_refresh_fallback=False)
    
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no autenticado")
    
    # Desactivar TODAS las sesiones activas
    await db.execute(
        update(AdminSession)
        .where(
            and_(
                AdminSession.user_id == user.id,
                AdminSession.is_active == True
            )
        )
        .values(is_active=False)
    )
    
    await db.commit()
    
    # Eliminar cookies
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("session_password_hash", path="/")
    response.delete_cookie("session_password_salt", path="/")
    
    return {"message": "Logout OK"}



@protected_router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [{"id": str(u.id), "email": u.email, "role": u.role} for u in users]



@protected_router.post("/users/block")
async def block_user(user_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(update(User).where(User.id == user_id).values(is_blocked=True))
    await db.commit()
    return {"status": "ok"}



@protected_router.post("/users/unblock")
async def unblock_user(user_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(update(User).where(User.id == user_id).values(is_blocked=False))
    await db.commit()
    return {"status": "ok"}



@protected_router.post("/users/admin")
async def make_admin(user_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(update(User).where(User.id == user_id).values(role="admin"))
    await db.commit()
    return {"status": "ok"}



@protected_router.post("/users/delete")
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
    return {"status": "ok"}



@protected_router.get("/ips")
async def get_ips(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AccessLog.ip_address, func.count().label("requests"))
        .group_by(AccessLog.ip_address)
        .order_by(func.count().desc())
    )
    return [{"ip": r[0], "requests": r[1]} for r in result.all()]



@protected_router.get("/visits")
async def visits(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Visit.ip_address, func.count(Visit.id).label("visits"))
        .group_by(Visit.ip_address)
    )
    return [{"ip": r.ip_address, "visits": r.visits} for r in result.all()]



@protected_router.get("/qa/logs")
async def qa_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(QueryLog))
    logs = result.scalars().all()
    return [{"id": str(l.id), "question": l.question} for l in logs]



@protected_router.get("/reviews")
async def reviews(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Review))
    rows = result.scalars().all()
    return [{"id": r.id, "rating": r.rating} for r in rows]



@protected_router.get("/messages")
async def contact_messages(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ContactMessage))
    messages = result.scalars().all()
    return [{"id": m.id, "email": m.email} for m in messages]



@protected_router.get("/ips/detail")
async def get_ips_detail(db: AsyncSession = Depends(get_db)):
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



@protected_router.get("/ips/users")
async def get_ips_users(db: AsyncSession = Depends(get_db)):
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



@protected_router.get("/top-endpoints")
async def top_endpoints(db: AsyncSession = Depends(get_db)):
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



@protected_router.get("/qa/out_of_domain")
async def get_out_of_domain_queries(
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene las consultas que fueron clasificadas como "out_of_domain"
    """
    result = await db.execute(
        select(QueryLog)
        .where(QueryLog.decision == "out_of_domain")
        .order_by(QueryLog.timestamp.desc())
        .limit(limit)
    )
    
    queries = result.scalars().all()
    
    return [
        {
            "id": str(q.id),
            "user_id": str(q.user_id) if q.user_id else None,
            "ip_address": q.ip_address,
            "question": q.question,
            "timestamp": q.timestamp.isoformat() if q.timestamp else None
        }
        for q in queries
    ]



@protected_router.get("/intentos-examen")
async def get_intentos_examen(
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """ recupera los intentos de examen detallando:
        ip, score, total, tiempo requerido, fecha de creacion
    """
    result = await db.execute(
        select(ExamAttempt)
        .order_by(ExamAttempt.created_at.desc())  
        .limit(limit)
    )
    attempts = result.scalars().all()
    
    return [
        {
            "id": str(a.id),
            "ip_address": a.ip_address,
            "score": a.score,
            "total": a.total,
            "duration_seconds": a.duration_seconds,  
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "user_id": str(a.user_id) if a.user_id else None,
            "anon_id": a.anon_id
        }
        for a in attempts
    ]