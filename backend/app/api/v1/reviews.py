"""
리뷰 API
────────
POST /api/v1/reviews/           리뷰 작성
GET  /api/v1/reviews/shop/{id}  샵 리뷰 목록
"""
from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.auth import get_current_user, require_role

router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewCreate(BaseModel):
    order_id:   UUID
    rating:     int  = Field(..., ge=1, le=5)
    comment:    Optional[str] = Field(None, max_length=500)


class ReviewOut(BaseModel):
    id:         str
    order_id:   str
    customer_name: str
    rating:     int
    comment:    Optional[str]
    created_at: str


@router.post("/", status_code=201)
async def create_review(
    req: ReviewCreate,
    current_user=Depends(require_role("CUSTOMER")),
    db: AsyncSession = Depends(get_db),
):
    # 주문이 완료 상태인지, 본인 주문인지 검증
    result = await db.execute(
        text("""
            SELECT id, status FROM orders
            WHERE id = :order_id AND customer_id = :customer_id
        """),
        {"order_id": req.order_id, "customer_id": current_user.id},
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")
    if order.status != "COMPLETED":
        raise HTTPException(400, "완료된 주문에만 리뷰를 작성할 수 있습니다")

    # 중복 리뷰 확인
    dup = await db.execute(
        text("SELECT id FROM reviews WHERE order_id = :order_id"),
        {"order_id": req.order_id},
    )
    if dup.fetchone():
        raise HTTPException(409, "이미 리뷰를 작성한 주문입니다")

    row = await db.execute(
        text("""
            INSERT INTO reviews (order_id, customer_id, rating, comment)
            VALUES (:order_id, :customer_id, :rating, :comment)
            RETURNING id
        """),
        {
            "order_id":    req.order_id,
            "customer_id": current_user.id,
            "rating":      req.rating,
            "comment":     req.comment,
        },
    )
    review_id = row.fetchone().id

    # 리뷰 포인트 적립 (+100P)
    await db.execute(
        text("""
            INSERT INTO point_transactions (user_id, amount, reason)
            VALUES (:uid, 100, '리뷰 작성')
        """),
        {"uid": str(current_user.id)}
    )

    # 샵 평점 및 리뷰 수 갱신
    await db.execute(
        text("""
            UPDATE shops s
            SET rating       = sub.avg_rating,
                review_count = sub.cnt,
                updated_at   = NOW()
            FROM (
                SELECT o.shop_id,
                       ROUND(AVG(r.rating)::numeric, 2) AS avg_rating,
                       COUNT(*) AS cnt
                FROM reviews r
                JOIN orders o ON o.id = r.order_id
                WHERE o.shop_id = (
                    SELECT shop_id FROM orders WHERE id = :order_id
                )
                GROUP BY o.shop_id
            ) sub
            WHERE s.id = sub.shop_id
        """),
        {"order_id": str(req.order_id)}
    )

    await db.commit()
    return {"id": str(review_id), "message": "리뷰가 등록되었습니다. (+100P)"}


@router.get("/shop/{shop_id}", response_model=List[ReviewOut])
async def list_shop_reviews(
    shop_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("""
            SELECT r.id, r.order_id, u.name AS customer_name,
                   r.rating, r.comment,
                   r.created_at::text AS created_at
            FROM reviews r
            JOIN orders o ON o.id = r.order_id
            JOIN users u  ON u.id = r.customer_id
            WHERE o.shop_id = :shop_id
            ORDER BY r.created_at DESC
            LIMIT 50
        """),
        {"shop_id": shop_id},
    )
    rows = result.mappings().all()
    return [
        {**dict(r), "id": str(r["id"]), "order_id": str(r["order_id"])}
        for r in rows
    ]
