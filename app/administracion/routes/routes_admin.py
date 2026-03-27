from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.administracion.security.admin_security import require_admin
from app.auth.database import get_db
from app.auth.models import User, AccessLog, Visit
from app.core.config import VALID_ROLES


router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_admin)]
)


# =========================
# USERS
# =========================
@router.get("/users")
async def get_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at
        }
        for u in users
    ]


@router.post("/users/{user_id}/role")
async def change_role(
    user_id: str,
    role: str,
    db: AsyncSession = Depends(get_db)
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

    return {"status": "ok", "new_role": role}


# =========================
# IPS
# =========================
@router.get("/ips")
async def get_ips(db: AsyncSession = Depends(get_db)):
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


@router.get("/ips/users")
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



@router.get("/top-endpoints")
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



@router.get("/visits")
async def get_visits(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Visit))
    visits = result.scalars().all()
    return [
        {
            "ip": v.ip_address,
            "first_visit": v.first_visit,
            "last_visit": v.last_visit,
            "visit_count": v.visit_count
        }
        for v in visits
    ]