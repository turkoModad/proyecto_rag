from fastapi import APIRouter, Request, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_db
from app.service import qa_cache
from app.routes.ask import get_real_ip


router = APIRouter()


@router.get("/usage")
async def get_usage(
    request: Request,
    current_user: dict | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    ip_address = get_real_ip(request)

    # USUARIO AUTENTICADO
    if current_user:
        limit_info = await qa_cache.check_user_limit(db, current_user)

        is_unlimited = limit_info["limit"] is None

        return {
            "used": limit_info["count"],
            "limit": None if is_unlimited else limit_info["limit"],
            "remaining": None if is_unlimited else limit_info["remaining"],
            "is_logged": True,
            "plan": current_user.get("role", "free"),  
            "is_unlimited": is_unlimited               
        }
    

    # USUARIO ANÓNIMO
    limit_info = await qa_cache.check_anonymous_limit(db, ip_address)

    return {
        "used": limit_info["count"],
        "limit": limit_info["limit"],
        "remaining": limit_info["remaining"],
        "is_logged": False,
        "plan": "anonymous",
        "is_unlimited": False
    }