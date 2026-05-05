"""
주문 API — FastAPI
──────────────────
POST   /api/v1/orders              주문 생성
GET    /api/v1/orders/{id}         주문 상세
PATCH  /api/v1/orders/{id}/status  상태 변경 (점주)
GET    /api/v1/partner/nearby-orders  반경 내 주문 목록
WS     /ws/orders/{id}            실시간 추적
"""
from __future__ import annotations
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field
from supabase import create_client
import asyncio

from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.config import settings
from app.models.order import Order, OrderStatus
from app.services.notification import send_nearby_partner_notifications
from app.services.geo import find_nearby_shops

router = APIRouter(prefix="/orders", tags=["orders"])

STORAGE_BUCKET = "order-photos"

def _get_supabase():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


# ── Schemas ────────────────────────────────────────────────────────────────────

class OrderCreateRequest(BaseModel):
    service_type:       str   = Field(..., pattern="^(DAY|NIGHT)$")
    wash_category:      str   = Field(..., pattern="^(CLOTHES_30L|CLOTHES_50L|BLANKET|SHOES)$")
    pickup_address:     str   = Field(..., min_length=5)
    pickup_lat:         float = Field(..., ge=33, le=43)    # 한국 위도 범위
    pickup_lng:         float = Field(..., ge=124, le=132)  # 한국 경도 범위
    delivery_address:   str   = Field(..., min_length=5)
    delivery_lat:       float
    delivery_lng:       float
    coupon_id:          Optional[UUID] = None
    customer_note:      Optional[str]  = None


class StatusUpdateRequest(BaseModel):
    new_status: OrderStatus
    note:       Optional[str] = None


class NearbyOrderResponse(BaseModel):
    order_id:       UUID
    wash_category:  str
    service_type:   str
    pickup_address: str
    distance_m:     float
    deadline_at:    datetime
    total_amount:   int
    hours_left:     float


# ── 가격표 ─────────────────────────────────────────────────────────────────────
PRICE_TABLE = {
    "CLOTHES_30L": 13000,
    "CLOTHES_50L": 18000,
    "BLANKET":     16000,
    "SHOES":       10000,
}

# 상태 전이 허용 맵 (점주가 바꿀 수 있는 전이)
PARTNER_TRANSITIONS = {
    OrderStatus.PENDING:    [OrderStatus.ACCEPTED],
    OrderStatus.ACCEPTED:   [OrderStatus.PICKED_UP],
    OrderStatus.PICKED_UP:  [OrderStatus.WASHING],
    OrderStatus.WASHING:    [OrderStatus.DRYING],
    OrderStatus.DRYING:     [OrderStatus.DELIVERING],
    OrderStatus.DELIVERING: [OrderStatus.COMPLETED],
}

# 사진 필수 상태
PHOTO_REQUIRED_STATUSES = {OrderStatus.PICKED_UP, OrderStatus.COMPLETED}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
async def create_order(
    req:        OrderCreateRequest,
    db:         AsyncSession = Depends(get_db),
    current_user = Depends(require_role("CUSTOMER")),
):
    """
    주문 생성
    1. 가격 계산 (쿠폰 적용)
    2. DB 저장 (deadline_at은 트리거가 자동 설정)
    3. 주변 점주에게 FCM 푸시 전송 (비동기)
    """
    base_amount = PRICE_TABLE[req.wash_category]
    discount = await _apply_coupon(db, req.coupon_id, base_amount, current_user.id) if req.coupon_id else 0
    total = base_amount - discount

    result = await db.execute(
        text("""
            INSERT INTO orders (
                customer_id, service_type, wash_category,
                pickup_address,  pickup_location,
                delivery_address, delivery_location,
                base_amount, discount_amount, total_amount,
                platform_fee, coupon_id, customer_note
            ) VALUES (
                :customer_id, :service_type::service_type, :wash_category::wash_category,
                :pickup_address,  ST_SetSRID(ST_MakePoint(:pickup_lng, :pickup_lat), 4326),
                :delivery_address, ST_SetSRID(ST_MakePoint(:delivery_lng, :delivery_lat), 4326),
                :base_amount, :discount, :total,
                1000, :coupon_id, :note
            )
            RETURNING id, deadline_at
        """),
        {
            "customer_id":    current_user.id,
            "service_type":   req.service_type,
            "wash_category":  req.wash_category,
            "pickup_address": req.pickup_address,
            "pickup_lat":     req.pickup_lat,
            "pickup_lng":     req.pickup_lng,
            "delivery_address": req.delivery_address,
            "delivery_lat":   req.delivery_lat,
            "delivery_lng":   req.delivery_lng,
            "base_amount":    base_amount,
            "discount":       discount,
            "total":          total,
            "coupon_id":      req.coupon_id,
            "note":           req.customer_note,
        }
    )
    row = result.fetchone()
    await db.commit()

    # 비동기로 주변 점주 알림 (응답 지연 없음)
    asyncio.create_task(
        send_nearby_partner_notifications(
            order_id=row.id,
            pickup_lat=req.pickup_lat,
            pickup_lng=req.pickup_lng,
            wash_category=req.wash_category,
            total_amount=total,
        )
    )

    return {"order_id": row.id, "deadline_at": row.deadline_at, "total_amount": total}


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id:   UUID,
    req:        StatusUpdateRequest,
    db:         AsyncSession = Depends(get_db),
    current_user = Depends(require_role("PARTNER")),
):
    """
    주문 상태 변경 (점주 전용)
    - PENDING → ACCEPTED: 낙관적 잠금으로 동시 수락 방지
    - PICKED_UP / COMPLETED: 증빙 사진 필수 검증
    """
    # 현재 주문 조회
    result = await db.execute(
        text("SELECT status, shop_id, version FROM orders WHERE id = :id FOR UPDATE"),
        {"id": order_id}
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")

    current_status = OrderStatus(order.status)
    allowed = PARTNER_TRANSITIONS.get(current_status, [])
    if req.new_status not in allowed:
        raise HTTPException(400, f"'{current_status}' 상태에서 '{req.new_status}'로 변경할 수 없습니다")

    # 사진 증빙 검증
    if req.new_status in PHOTO_REQUIRED_STATUSES:
        photo_type = "PICKUP" if req.new_status == OrderStatus.PICKED_UP else "DELIVERY"
        photo_check = await db.execute(
            text("SELECT id FROM order_photos WHERE order_id = :oid AND photo_type = :ptype LIMIT 1"),
            {"oid": order_id, "ptype": photo_type}
        )
        if not photo_check.fetchone():
            raise HTTPException(
                400,
                f"{'수거' if photo_type == 'PICKUP' else '배송'} 증빙 사진을 먼저 업로드해 주세요"
            )

    # ACCEPTED: 낙관적 잠금 수락 함수 사용
    if req.new_status == OrderStatus.ACCEPTED:
        accepted = await db.execute(
            text("SELECT accept_order(:oid, :shop_id, :ver)"),
            {"oid": order_id, "shop_id": current_user.shop_id, "ver": order.version}
        )
        if not accepted.scalar():
            raise HTTPException(409, "이미 다른 점주가 수락한 주문입니다")
        await db.commit()
        return {"success": True, "status": req.new_status}

    # 일반 상태 전이
    ts_col = {
        OrderStatus.PICKED_UP:  "picked_up_at",
        OrderStatus.COMPLETED:  "completed_at",
    }.get(req.new_status)

    ts_set = f", {ts_col} = NOW()" if ts_col else ""
    await db.execute(
        text(f"UPDATE orders SET status = :s::order_status{ts_set}, updated_at = NOW() WHERE id = :id"),
        {"s": req.new_status.value, "id": order_id}
    )
    await db.commit()

    # Supabase Realtime이 orders 테이블 UPDATE를 구독자에게 자동 브로드캐스트

    return {"success": True, "status": req.new_status}


@router.post("/{order_id}/photos")
async def upload_order_photo(
    order_id:   UUID,
    photo_type: str,
    file:       UploadFile = File(...),
    db:         AsyncSession = Depends(get_db),
    current_user = Depends(require_role("PARTNER")),
):
    """
    S3 증빙 사진 업로드
    - 파일 타입 검증 (JPEG/PNG만 허용)
    - S3 업로드 후 DB에 메타데이터 저장
    """
    allowed_types = {"image/jpeg", "image/png"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "JPEG 또는 PNG 파일만 업로드할 수 있습니다")

    if file.size > 10 * 1024 * 1024:  # 10MB 제한
        raise HTTPException(413, "파일 크기는 10MB 이하여야 합니다")

    ext = "jpg" if file.content_type == "image/jpeg" else "png"
    storage_path = f"photos/{order_id}/{photo_type.lower()}/{int(datetime.now(timezone.utc).timestamp())}.{ext}"

    content = await file.read()

    # Supabase Storage 업로드 (동기 클라이언트를 스레드에서 실행)
    def _upload():
        sb = _get_supabase()
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type, "upsert": "false"},
        )
        return sb.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)

    view_url = await asyncio.to_thread(_upload)

    # DB 저장 (s3_key 컬럼에 storage_path, s3_bucket 컬럼에 버킷명 저장)
    await db.execute(
        text("""
            INSERT INTO order_photos (order_id, uploader_id, photo_type, s3_key, s3_bucket)
            VALUES (:order_id, :uploader_id, :photo_type::photo_type, :s3_key, :bucket)
        """),
        {
            "order_id":    order_id,
            "uploader_id": current_user.id,
            "photo_type":  photo_type.upper(),
            "s3_key":      storage_path,
            "bucket":      STORAGE_BUCKET,
        }
    )
    await db.commit()

    return {"storage_path": storage_path, "view_url": view_url}


@router.get("/partner/nearby", response_model=list[NearbyOrderResponse])
async def get_nearby_orders(
    db:         AsyncSession = Depends(get_db),
    current_user = Depends(require_role("PARTNER")),
):
    """
    점주 반경 내 대기 주문 목록 (PostGIS)
    """
    result = await db.execute(
        text("SELECT * FROM get_nearby_orders(:shop_id, 30)"),
        {"shop_id": current_user.shop_id}
    )
    rows = result.fetchall()
    now = datetime.now(timezone.utc)
    return [
        NearbyOrderResponse(
            order_id=r.order_id,
            wash_category=r.wash_category,
            service_type=r.service_type,
            pickup_address=r.pickup_address,
            distance_m=round(r.distance_m, 1),
            deadline_at=r.deadline_at,
            total_amount=r.total_amount,
            hours_left=round((r.deadline_at - now).total_seconds() / 3600, 1),
        )
        for r in rows
    ]



async def _apply_coupon(db, coupon_id, base_amount, user_id) -> int:
    """쿠폰 유효성 검증 및 할인액 반환"""
    result = await db.execute(
        text("""
            SELECT c.discount_amount, c.discount_rate, c.min_order_amount
            FROM coupons c
            JOIN user_coupons uc ON uc.coupon_id = c.id
            WHERE c.id = :cid AND uc.user_id = :uid
              AND uc.used_at IS NULL AND c.is_active
              AND (c.expires_at IS NULL OR c.expires_at > NOW())
        """),
        {"cid": coupon_id, "uid": user_id}
    )
    coupon = result.fetchone()
    if not coupon:
        raise HTTPException(400, "유효하지 않은 쿠폰입니다")
    if base_amount < coupon.min_order_amount:
        raise HTTPException(400, f"최소 주문 금액 {coupon.min_order_amount:,}원 이상이어야 합니다")
    if coupon.discount_amount:
        return coupon.discount_amount
    if coupon.discount_rate:
        return int(base_amount * coupon.discount_rate / 100)
    return 0

