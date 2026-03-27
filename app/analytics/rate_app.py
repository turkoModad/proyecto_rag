# app/analytics/rate_app.py
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.auth.database import get_db
from app.auth.models import Review, User
from app.auth.dependencies import get_current_user_db
from app.utils.network import get_real_ip
from app.auth.service import has_review_recently  
from sqlalchemy import func, select

# Constante para período de valoración semanal
REVIEW_COOLDOWN_DAYS = 7

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/create")
async def create_review(
    request: Request,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_db)
):
    rating = payload.get("rating")
    comment = payload.get("comment")

    try:
        rating = int(rating)
    except:
        raise HTTPException(status_code=400, detail="Rating inválido")

    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Rating inválido")

    ip = get_real_ip(request)

    # Verificar si ya valoró en los últimos 7 días (semanal)
    already_reviewed = await has_review_recently(
        db,
        current_user.id if current_user else None,
        ip,
        days=REVIEW_COOLDOWN_DAYS
    )

    if already_reviewed:
        raise HTTPException(
            status_code=400,
            detail=f"Solo puedes valorar una vez cada {REVIEW_COOLDOWN_DAYS} días (una vez por semana). Vuelve a intentarlo en unos días."
        )

    review = Review(
        user_id=current_user.id if current_user else None,
        ip_address=ip,
        rating=rating,
        comment=comment
    )

    try:
        db.add(review)
        await db.commit()

    except IntegrityError as e:
        await db.rollback()

        if "unique_user_review" in str(e):
            detail = "Ya valoraste con esta cuenta"
        elif "unique_ip_review_anonymous" in str(e):
            detail = "Ya enviaste una valoración desde esta conexión"
        else:
            detail = "Error al guardar valoración"

        raise HTTPException(status_code=400, detail=detail)

    return {"message": "Review guardada correctamente"}


@router.get("/me")
async def get_my_review(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_db)
):
    ip = get_real_ip(request)

    has_review = await has_review_recently(
        db,
        current_user.id if current_user else None,
        ip,
        days=REVIEW_COOLDOWN_DAYS
    )

    return {
        "has_review": has_review
    }


@router.get("/stats")
async def get_review_stats(
    db: AsyncSession = Depends(get_db)
):
    """Obtiene estadísticas de valoraciones: promedio y total"""
    
    total_count_query = select(func.count(Review.id))
    total_count_result = await db.execute(total_count_query)
    total_reviews = total_count_result.scalar() or 0
    
    if total_reviews > 0:
        avg_query = select(func.avg(Review.rating))
        avg_result = await db.execute(avg_query)
        avg_rating = round(avg_result.scalar() or 0, 1)
    else:
        avg_rating = 0
    
    return {
        "avg_rating": avg_rating,
        "total_reviews": total_reviews
    }