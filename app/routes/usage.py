from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, get_db
from app.auth.service import count_user_queries, count_anonymous_queries
from app.routes.ask import get_real_ip
from app.core.config import LIMITE_CON_AUTH, LIMITE_SIN_AUTH

router = APIRouter()


@router.get("/usage")
async def get_usage(
    request: Request,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):

    ip_address = get_real_ip(request)

    if current_user:
        used = await count_user_queries(db, current_user["sub"])
        limit = LIMITE_CON_AUTH
        remaining = max(limit - used, 0)

        return {
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "is_logged": True
        }

    else:
        used = await count_anonymous_queries(db, ip_address, "/ask")
        limit = LIMITE_SIN_AUTH
        remaining = max(limit - used, 0)

        return {
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "is_logged": False
        }