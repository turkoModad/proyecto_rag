from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime


from app.auth.database import get_db 

app = FastAPI()


class ReviewCreate(BaseModel):
    username: str
    comment: str
    rating: int


class ReviewOut(BaseModel):
    id: int
    username: str
    comment: str
    rating: int
    created_at: datetime


@app.post("/api/reviews", response_model=ReviewOut)
async def create_review(review: ReviewCreate, db: AsyncSession = Depends(get_db)):
    if review.rating < 1 or review.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")
    result = await db.execute(
        "INSERT INTO reviews (username, comment, rating) VALUES (:username, :comment, :rating) RETURNING id, username, comment, rating, created_at",
        {"username": review.username, "comment": review.comment, "rating": review.rating}
    )
    row = result.fetchone()
    await db.commit()
    return dict(row)


@app.get("/api/reviews", response_model=list[ReviewOut])
async def get_reviews(db: AsyncSession = Depends(get_db)):
    result = await db.execute("SELECT id, username, comment, rating, created_at FROM reviews ORDER BY created_at DESC")
    return [dict(r) for r in result.fetchall()]