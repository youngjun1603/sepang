"""
사용자 API
──────────
GET   /api/v1/users/me                내 프로필 조회
PATCH /api/v1/users/me                프로필 수정
GET   /api/v1/users/me/points         포인트 잔액 + 최근 내역
GET   /api/v1/users/me/coupons        보유 쿠폰 목록
POST  /api/v1/users/me/push-subscription  Web Push 구독 등록
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user, require_role

router = APIRouter(prefix="/users", tags=["users"])


class ProfileUpdate(BaseModel):
    name:    Optional[str] = None
    address: Optional[str] = None


class AvailabilityUpdate(BaseModel):
    is_available: bool


class PushSubscription(BaseModel):
    endpoint:   str
    p256dh_key: str
    auth_key:   str

class FcmTokenRequest(BaseModel):
    fcm_token: str


@router.get("/me")
async def get_me(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT u.id, u.name, u.phone, u.email, u.role, u.created_at,
                   s.name AS shop_name, s.rating
            FROM users u
            LEFT JOIN shops s ON s.owner_id = u.id
            WHERE u.id = :id
        """),
        {"id": current_user.id},
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    row = dict(user._mapping)
    row["id"] = str(row["id"])
    return row


@router.patch("/me")
async def update_me(
    req: ProfileUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "수정할 항목을 입력해 주세요")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    await db.execute(
        text(f"UPDATE users SET {set_clause} WHERE id = :id"),
        {**updates, "id": current_user.id},
    )
    await db.commit()
    return {"success": True}


@router.get("/me/points")
async def get_points(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """포인트 잔액 + 최근 20건 트랜잭션"""
    balance_row = await db.execute(
        text("""
            SELECT COALESCE(balance, 0) AS balance
            FROM point_transactions
            WHERE user_id = :uid
            ORDER BY id DESC LIMIT 1
        """),
        {"uid": current_user.id},
    )
    balance = (balance_row.fetchone() or (0,))[0]

    history_rows = await db.execute(
        text("""
            SELECT amount, balance, reason, created_at::text AS created_at
            FROM point_transactions
            WHERE user_id = :uid
            ORDER BY id DESC LIMIT 20
        """),
        {"uid": current_user.id},
    )
    history = [dict(r._mapping) for r in history_rows.fetchall()]

    return {"balance": int(balance), "history": history}


@router.get("/me/coupons")
async def get_coupons(current_user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """보유 쿠폰 목록 (미사용 + 유효기간 내)"""
    rows = await db.execute(
        text("""
            SELECT c.id, c.name, c.code,
                   c.discount_amount, c.discount_rate,
                   c.min_order_amount, c.expires_at::text AS expires_at
            FROM user_coupons uc
            JOIN coupons c ON c.id = uc.coupon_id
            WHERE uc.user_id = :uid
              AND uc.used_at IS NULL
              AND c.is_active = true
              AND (c.expires_at IS NULL OR c.expires_at > NOW())
            ORDER BY c.expires_at ASC NULLS LAST
        """),
        {"uid": current_user.id},
    )
    coupons = [
        {**dict(r._mapping), "id": str(r["id"])}
        for r in rows.fetchall()
    ]
    return {"coupons": coupons, "count": len(coupons)}


@router.get("/me/availability")
async def get_availability(
    current_user=Depends(require_role("PARTNER")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("SELECT is_available FROM shops WHERE owner_id = :uid"),
        {"uid": current_user.id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "점포를 찾을 수 없습니다")
    return {"is_available": row.is_available}


@router.patch("/me/availability")
async def set_availability(
    req: AvailabilityUpdate,
    current_user=Depends(require_role("PARTNER")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("UPDATE shops SET is_available = :v WHERE owner_id = :uid RETURNING id"),
        {"v": req.is_available, "uid": current_user.id},
    )
    if not result.fetchone():
        raise HTTPException(404, "점포를 찾을 수 없습니다")
    await db.commit()
    return {"is_available": req.is_available}


@router.patch("/me/fcm-token", status_code=200)
async def save_fcm_token(
    req: FcmTokenRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("UPDATE users SET fcm_token = :token WHERE id = :id"),
        {"token": req.fcm_token, "id": current_user.id},
    )
    await db.commit()
    return {"success": True}


@router.post("/me/push-subscription", status_code=201)
async def save_push_subscription(
    req: PushSubscription,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("""
            INSERT INTO push_subscriptions (user_id, endpoint, p256dh_key, auth_key)
            VALUES (:user_id, :endpoint, :p256dh, :auth)
            ON CONFLICT (endpoint) DO UPDATE
            SET p256dh_key = :p256dh, auth_key = :auth, updated_at = NOW()
        """),
        {
            "user_id":  current_user.id,
            "endpoint": req.endpoint,
            "p256dh":   req.p256dh_key,
            "auth":     req.auth_key,
        },
    )
    await db.commit()
    return {"success": True}
