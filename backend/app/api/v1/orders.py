"""
주문 API — FastAPI
──────────────────
POST   /api/v1/orders                주문 생성
POST   /api/v1/orders/{id}/cancel    주문 취소 (고객, PENDING/ACCEPTED만)
GET    /api/v1/orders/{id}           주문 상세
PATCH  /api/v1/orders/{id}/status    상태 변경 (점주)
POST   /api/v1/orders/{id}/reject    주문 거절 (점주)
POST   /api/v1/orders/{id}/photos    사진 업로드
GET    /api/v1/orders/partner/nearby 반경 내 주문 목록
"""
from __future__ import annotations
import base64
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone

import httpx
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
from app.services.notification import send_nearby_partner_notifications, send_customer_status_notification, send_sms
from app.services.geo import find_nearby_shops
from app.services.weather import get_weather_multiplier

router = APIRouter(prefix="/orders", tags=["orders"])

STORAGE_BUCKET = "order-photos"

def _get_supabase():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)

def _toss_headers() -> dict:
    encoded = base64.b64encode(f"{settings.TOSS_SECRET_KEY}:".encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}


# ── Schemas ────────────────────────────────────────────────────────────────────

class OrderCreateRequest(BaseModel):
    service_type:       str   = Field(..., pattern="^(DAY|NIGHT)$")
    wash_category:      str   = Field(..., min_length=2, max_length=50, pattern=r"^[A-Z0-9_]+$")
    pickup_address:     str   = Field(..., min_length=5)
    pickup_lat:         float = Field(..., ge=33, le=43)
    pickup_lng:         float = Field(..., ge=124, le=132)
    delivery_address:   str   = Field(..., min_length=5)
    delivery_lat:       float
    delivery_lng:       float
    coupon_id:          Optional[UUID] = None
    use_points:         bool           = False
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


class OrderOut(BaseModel):
    id:               UUID
    customer_id:      UUID
    shop_id:          Optional[UUID] = None
    service_type:     str
    wash_category:    str
    status:           str
    pickup_address:   str
    delivery_address: str
    total_amount:     int
    platform_fee:     int
    ordered_at:       datetime
    deadline_at:      Optional[datetime] = None
    picked_up_at:     Optional[datetime] = None
    completed_at:     Optional[datetime] = None
    customer_note:    Optional[str] = None


# ── 상태 전이 허용 맵 (점주) ───────────────────────────────────────────────────
PARTNER_TRANSITIONS = {
    OrderStatus.PENDING:    [OrderStatus.ACCEPTED],
    OrderStatus.ACCEPTED:   [OrderStatus.PICKED_UP],
    OrderStatus.PICKED_UP:  [OrderStatus.WASHING],
    OrderStatus.WASHING:    [OrderStatus.DRYING],
    OrderStatus.DRYING:     [OrderStatus.DELIVERING],
    OrderStatus.DELIVERING: [OrderStatus.COMPLETED],
}

PHOTO_REQUIRED_STATUSES = {OrderStatus.PICKED_UP, OrderStatus.COMPLETED}

_CUSTOMER_NOTIFY = {
    "ACCEPTED":   ("수락 완료 ✅", "점주가 주문을 수락했습니다. 잠시 후 수거 예정이에요 🧺"),
    "PICKED_UP":  ("수거 완료 🧺", "세탁물을 수거했습니다. 열심히 세탁할게요!"),
    "WASHING":    ("세탁 시작 🫧", "세탁이 시작됐습니다. 곧 깔끔해질 거예요!"),
    "DELIVERING": ("배송 출발 🚗", "세탁 완료! 지금 배송 중이에요."),
    "COMPLETED":  ("배송 완료 🎉", "세탁물이 도착했어요. 리뷰를 남겨주세요 ⭐"),
    "CANCELLED":  ("주문 취소 ❌", "주문이 취소되었습니다."),
}

# 고객이 취소 가능한 상태 (수거 전)
CUSTOMER_CANCELLABLE = {"PENDING", "ACCEPTED"}
# 관리자도 취소 불가능한 최종 상태
ADMIN_NON_CANCELLABLE = {"CANCELLED", "COMPLETED"}


async def _sms_order_event(customer_id: str, message: str) -> None:
    """주문 이벤트 SMS — SENS 설정 시에만 발송, 실패해도 무시"""
    if not settings.NAVER_SENS_SERVICE_ID:
        return
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as _db:
        row = await _db.execute(text("SELECT phone FROM users WHERE id = :id"), {"id": customer_id})
        phone = row.scalar()
        if phone:
            try:
                await send_sms(phone, message)
            except Exception:
                pass


# ── 공통 취소 로직 ─────────────────────────────────────────────────────────────

async def _do_cancel_order(db: AsyncSession, order, reason: str) -> None:
    """주문 취소 + 쿠폰/포인트 복원 + Toss 환불 (결제 완료 시)"""
    oid = order.id

    await db.execute(
        text("""
            UPDATE orders
            SET status = 'CANCELLED', cancelled_at = NOW(),
                cancel_reason = :reason, updated_at = NOW()
            WHERE id = :id
        """),
        {"reason": reason, "id": oid},
    )

    if order.coupon_id:
        await db.execute(
            text("UPDATE user_coupons SET used_at = NULL, order_id = NULL WHERE coupon_id = :cid AND user_id = :uid"),
            {"cid": order.coupon_id, "uid": order.customer_id},
        )

    points_used = getattr(order, "points_used", 0) or 0
    if points_used > 0:
        bal_row = await db.execute(
            text("SELECT COALESCE(balance, 0) FROM point_transactions WHERE user_id = :uid ORDER BY id DESC LIMIT 1"),
            {"uid": order.customer_id},
        )
        cur_bal = (bal_row.fetchone() or (0,))[0]
        await db.execute(
            text("""
                INSERT INTO point_transactions (user_id, amount, balance, reason, order_id)
                VALUES (:uid, :amt, :bal, '주문 취소 포인트 환불', :oid)
            """),
            {"uid": order.customer_id, "amt": points_used, "bal": cur_bal + points_used, "oid": oid},
        )

    payment_status = getattr(order, "payment_status", None)
    payment_key    = getattr(order, "payment_key", None)
    if payment_status == "PAID" and payment_key and settings.TOSS_SECRET_KEY:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.tosspayments.com/v1/payments/{payment_key}/cancel",
                headers=_toss_headers(),
                json={"cancelReason": reason},
            )
        if resp.status_code == 200:
            await db.execute(
                text("UPDATE orders SET payment_status = 'REFUNDED' WHERE id = :id"),
                {"id": oid},
            )
            await db.execute(
                text("UPDATE payment_transactions SET status = 'REFUNDED', cancel_reason = :r, updated_at = NOW() WHERE order_id = :oid"),
                {"r": reason, "oid": oid},
            )

    await db.commit()

    # 취소 알림: 고객 + 점주 (담당 점포가 있을 때)
    notif_rows = await db.execute(
        text("""
            SELECT
                cu.fcm_token AS customer_fcm,
                cu.id::text  AS customer_id,
                pu.fcm_token AS partner_fcm,
                pu.id::text  AS partner_id
            FROM orders o
            JOIN users cu ON cu.id = o.customer_id
            LEFT JOIN shops  sh ON sh.id = o.shop_id
            LEFT JOIN users pu ON pu.id = sh.owner_id
            WHERE o.id = :oid
        """),
        {"oid": oid},
    )
    notif = notif_rows.fetchone()
    if notif:
        cancel_title = "주문 취소 ❌"
        asyncio.create_task(
            send_customer_status_notification(
                notif.customer_id, notif.customer_fcm, str(oid),
                cancel_title, "주문이 취소되었습니다.",
            )
        )
        if notif.partner_fcm:
            asyncio.create_task(
                send_customer_status_notification(
                    notif.partner_id, notif.partner_fcm, str(oid),
                    "담당 주문 취소 ❌", f"담당 주문이 취소되었습니다. ({reason})",
                )
            )
        asyncio.create_task(
            _sms_order_event(notif.customer_id, f"[세팡] 주문이 취소되었습니다. (#{str(oid)[-6:].upper()})")
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
async def create_order(
    req:         OrderCreateRequest,
    db:          AsyncSession = Depends(get_db),
    current_user = Depends(require_role("CUSTOMER")),
):
    """
    주문 생성
    1. wash_items 테이블에서 가격 동적 조회
    2. 쿠폰/포인트 적용
    3. DB 저장 (deadline_at은 트리거 자동 설정)
    4. 주변 점주 FCM 알림 (비동기)
    """
    price_row = await db.execute(
        text("SELECT base_price FROM wash_items WHERE key = :key AND is_active = true"),
        {"key": req.wash_category},
    )
    item = price_row.fetchone()
    if not item:
        raise HTTPException(400, f"유효하지 않은 세탁 품목입니다: {req.wash_category}")
    base_amount = item.base_price

    # ── 날씨 요금 적용 ─────────────────────────────────────────
    weather_condition, weather_multiplier = await get_weather_multiplier(
        req.pickup_lat, req.pickup_lng, db
    )
    weather_amount = int(round(base_amount * weather_multiplier))

    # ── 거리 요금 적용 (가장 가까운 활성 매장 기준) ─────────────
    distance_km = 0.0
    distance_surcharge = 0
    nearby = await find_nearby_shops(db, req.pickup_lat, req.pickup_lng, radius_m=5000)
    if nearby:
        distance_km = round(nearby[0]["distance_m"] / 1000, 3)
        dist_row = await db.execute(
            text("""
                SELECT surcharge FROM distance_pricing
                WHERE is_active = true
                  AND min_km <= :km
                  AND (max_km IS NULL OR max_km > :km)
                ORDER BY min_km DESC
                LIMIT 1
            """),
            {"km": distance_km},
        )
        dist_result = dist_row.fetchone()
        if dist_result:
            distance_surcharge = dist_result.surcharge

    # 날씨 + 거리 적용된 기준 금액
    adjusted_base = weather_amount + distance_surcharge

    discount = await _apply_coupon(db, req.coupon_id, adjusted_base, current_user.id) if req.coupon_id else 0
    after_coupon = max(0, adjusted_base - discount)  # 쿠폰 과할인 방어

    points_used = 0
    point_balance = 0
    if req.use_points:
        pts = await db.execute(
            text("SELECT COALESCE((SELECT balance FROM point_transactions WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1), 0)"),
            {"uid": current_user.id},
        )
        point_balance = pts.scalar() or 0
        if point_balance > 0:
            points_used = min(point_balance, after_coupon)  # after_coupon이 0이면 포인트도 0

    total = max(0, after_coupon - points_used)  # 최종 음수 방어

    result = await db.execute(
        text("""
            INSERT INTO orders (
                customer_id, service_type, wash_category,
                pickup_address,  pickup_location,
                delivery_address, delivery_location,
                base_amount, discount_amount, total_amount,
                platform_fee, coupon_id, customer_note, points_used,
                weather_condition, weather_multiplier,
                distance_km, distance_surcharge
            ) VALUES (
                :customer_id, CAST(:service_type AS service_type), :wash_category,
                :pickup_address,  ST_SetSRID(ST_MakePoint(:pickup_lng, :pickup_lat), 4326),
                :delivery_address, ST_SetSRID(ST_MakePoint(:delivery_lng, :delivery_lat), 4326),
                :base_amount, :total_discount, :total,
                1000, :coupon_id, :note, :points_used,
                :weather_condition, :weather_multiplier,
                :distance_km, :distance_surcharge
            )
            RETURNING id, deadline_at
        """),
        {
            "customer_id":        current_user.id,
            "service_type":       req.service_type,
            "wash_category":      req.wash_category,
            "pickup_address":     req.pickup_address,
            "pickup_lat":         req.pickup_lat,
            "pickup_lng":         req.pickup_lng,
            "delivery_address":   req.delivery_address,
            "delivery_lat":       req.delivery_lat,
            "delivery_lng":       req.delivery_lng,
            "base_amount":        base_amount,
            "total_discount":     discount + points_used,
            "total":              total,
            "coupon_id":          req.coupon_id,
            "note":               req.customer_note,
            "points_used":        points_used,
            "weather_condition":  weather_condition if weather_condition != "NONE" else None,
            "weather_multiplier": weather_multiplier,
            "distance_km":        distance_km,
            "distance_surcharge": distance_surcharge,
        }
    )
    row = result.fetchone()

    if points_used > 0:
        await db.execute(
            text("""
                INSERT INTO point_transactions (user_id, amount, balance, reason, order_id)
                VALUES (:uid, :amount, :balance, :reason, :oid)
            """),
            {
                "uid":     current_user.id,
                "amount":  -points_used,
                "balance": point_balance - points_used,
                "reason":  "주문 시 포인트 사용",
                "oid":     row.id,
            },
        )

    if req.coupon_id:
        await db.execute(
            text("UPDATE user_coupons SET used_at = NOW(), order_id = :oid WHERE coupon_id = :cid AND user_id = :uid"),
            {"oid": row.id, "cid": req.coupon_id, "uid": current_user.id},
        )

    await db.commit()

    asyncio.create_task(
        send_nearby_partner_notifications(
            order_id=row.id,
            pickup_lat=req.pickup_lat,
            pickup_lng=req.pickup_lng,
            wash_category=req.wash_category,
            total_amount=total,
        )
    )
    asyncio.create_task(
        _sms_order_event(
            str(current_user.id),
            f"[세팡] 주문이 접수되었습니다 (#{str(row.id)[-6:].upper()}). 수거 예정까지 대기해 주세요.",
        )
    )

    return {
        "order_id":    row.id,
        "deadline_at": row.deadline_at,
        "total_amount": total,
        "price_breakdown": {
            "base_amount":        base_amount,
            "weather_condition":  weather_condition,
            "weather_multiplier": weather_multiplier,
            "weather_surcharge":  weather_amount - base_amount,
            "distance_km":        distance_km,
            "distance_surcharge": distance_surcharge,
            "coupon_discount":    discount,
            "points_used":        points_used,
            "total":              total,
        },
    }


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id:    UUID,
    db:          AsyncSession = Depends(get_db),
    current_user = Depends(require_role("CUSTOMER")),
):
    """고객 주문 취소 — PENDING / ACCEPTED 상태만 가능"""
    result = await db.execute(
        text("""
            SELECT id, status::text, customer_id, coupon_id, points_used,
                   payment_status::text, payment_key
            FROM orders WHERE id = :id
        """),
        {"id": order_id},
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")
    if str(order.customer_id) != str(current_user.id):
        raise HTTPException(403, "본인 주문만 취소할 수 있습니다")
    if order.status not in CUSTOMER_CANCELLABLE:
        raise HTTPException(400, "수거 전(접수·수락) 주문만 취소할 수 있습니다")

    await _do_cancel_order(db, order, "고객 취소")
    return {"success": True}


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
    result = await db.execute(
        text("""
            SELECT o.status, o.shop_id, o.version, o.customer_id, u.fcm_token
            FROM orders o
            JOIN users u ON u.id = o.customer_id
            WHERE o.id = :id FOR UPDATE
        """),
        {"id": order_id},
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")

    current_status = OrderStatus(order.status)

    if req.new_status == OrderStatus.ACCEPTED and current_status != OrderStatus.PENDING:
        raise HTTPException(409, "이미 다른 점주가 수락한 주문입니다")

    allowed = PARTNER_TRANSITIONS.get(current_status, [])
    if req.new_status not in allowed:
        raise HTTPException(400, f"'{current_status}' 상태에서 '{req.new_status}'로 변경할 수 없습니다")

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

    if req.new_status == OrderStatus.ACCEPTED:
        accepted = await db.execute(
            text("SELECT accept_order(:oid, :shop_id, :ver)"),
            {"oid": order_id, "shop_id": current_user.shop_id, "ver": order.version}
        )
        if not accepted.scalar():
            raise HTTPException(409, "이미 다른 점주가 수락한 주문입니다")
        await db.commit()
        if "ACCEPTED" in _CUSTOMER_NOTIFY:
            title, body = _CUSTOMER_NOTIFY["ACCEPTED"]
            asyncio.create_task(
                send_customer_status_notification(str(order.customer_id), order.fcm_token, str(order_id), title, body)
            )
        asyncio.create_task(
            _sms_order_event(str(order.customer_id), f"[세팡] 점주가 주문을 수락했습니다. 곧 수거 예정이에요 (#{str(order_id)[-6:].upper()})")
        )
        return {"success": True, "status": req.new_status}

    ts_col = {
        OrderStatus.PICKED_UP:  "picked_up_at",
        OrderStatus.COMPLETED:  "completed_at",
    }.get(req.new_status)

    ts_set = f", {ts_col} = NOW()" if ts_col else ""
    await db.execute(
        text(f"UPDATE orders SET status = CAST(:s AS order_status){ts_set}, updated_at = NOW() WHERE id = :id"),
        {"s": req.new_status.value, "id": order_id}
    )
    await db.commit()

    status_key = req.new_status.value
    if status_key in _CUSTOMER_NOTIFY:
        title, body = _CUSTOMER_NOTIFY[status_key]
        asyncio.create_task(
            send_customer_status_notification(str(order.customer_id), order.fcm_token, str(order_id), title, body)
        )
    if status_key == "COMPLETED":
        asyncio.create_task(
            _sms_order_event(str(order.customer_id), f"[세팡] 세탁이 완료되어 배송되었습니다! 리뷰를 남겨주세요 ⭐ (#{str(order_id)[-6:].upper()})")
        )

    return {"success": True, "status": req.new_status}


@router.post("/{order_id}/photos")
async def upload_order_photo(
    order_id:   UUID,
    photo_type: str,
    file:       UploadFile = File(...),
    db:         AsyncSession = Depends(get_db),
    current_user = Depends(require_role("PARTNER")),
):
    allowed_types = {"image/jpeg", "image/png"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, "JPEG 또는 PNG 파일만 업로드할 수 있습니다")

    if file.size > 10 * 1024 * 1024:
        raise HTTPException(413, "파일 크기는 10MB 이하여야 합니다")

    ext = "jpg" if file.content_type == "image/jpeg" else "png"
    storage_path = f"photos/{order_id}/{photo_type.lower()}/{int(datetime.now(timezone.utc).timestamp())}.{ext}"

    content = await file.read()

    def _upload():
        sb = _get_supabase()
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type, "upsert": "false"},
        )
        return sb.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)

    view_url = await asyncio.to_thread(_upload)

    await db.execute(
        text("""
            INSERT INTO order_photos (order_id, uploader_id, photo_type, s3_key, s3_bucket)
            VALUES (:order_id, :uploader_id, CAST(:photo_type AS photo_type), :s3_key, :bucket)
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
    db:          AsyncSession = Depends(get_db),
    current_user = Depends(require_role("PARTNER")),
):
    if not current_user.shop_id:
        raise HTTPException(400, "등록된 매장이 없습니다. 관리자에게 문의하세요.")
    result = await db.execute(
        text("SELECT * FROM get_nearby_orders(:shop_id, 3)"),
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


@router.get("/", response_model=list[OrderOut])
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.role == "PARTNER":
        result = await db.execute(
            text("""
                SELECT o.id, o.customer_id, o.shop_id,
                       o.service_type::text, o.wash_category::text, o.status::text,
                       o.pickup_address, o.delivery_address,
                       o.total_amount, o.platform_fee, o.ordered_at, o.deadline_at,
                       o.picked_up_at, o.completed_at, o.customer_note
                FROM orders o
                JOIN shops s ON s.id = o.shop_id
                WHERE s.owner_id = :uid
                ORDER BY o.ordered_at DESC
                LIMIT 100
            """),
            {"uid": current_user.id},
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, customer_id, shop_id,
                       service_type::text, wash_category::text, status::text,
                       pickup_address, delivery_address,
                       total_amount, platform_fee, ordered_at, deadline_at,
                       picked_up_at, completed_at, customer_note
                FROM orders
                WHERE customer_id = :uid
                ORDER BY ordered_at DESC
                LIMIT 100
            """),
            {"uid": current_user.id},
        )
    return [dict(r._mapping) for r in result.fetchall()]


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        text("""
            SELECT id, customer_id, shop_id, service_type::text, wash_category::text,
                   status::text, pickup_address, delivery_address,
                   total_amount, platform_fee, ordered_at, deadline_at,
                   picked_up_at, completed_at, customer_note
            FROM orders
            WHERE id = :id
              AND (customer_id = :uid OR shop_id IN (
                  SELECT id FROM shops WHERE owner_id = :uid
              ))
        """),
        {"id": order_id, "uid": current_user.id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "주문을 찾을 수 없습니다")
    return dict(row._mapping)


class RejectOrderRequest(BaseModel):
    reason: Optional[str] = None


async def _record_penalty(
    db: AsyncSession,
    shop_id: str,
    order_id,
    penalty_type: str,
    penalty_point: int,
    description: str,
) -> None:
    """패널티 기록 + 누적 점수 반영 (10점 초과 시 자동 정지)"""
    await db.execute(
        text("""
            INSERT INTO partner_penalties (shop_id, order_id, penalty_type, penalty_point, description)
            VALUES (:shop_id, :order_id, :ptype, :point, :desc)
        """),
        {
            "shop_id":  shop_id,
            "order_id": order_id,
            "ptype":    penalty_type,
            "point":    penalty_point,
            "desc":     description,
        },
    )
    await db.execute(
        text("""
            UPDATE shops
            SET penalty_score = penalty_score + :point,
                -- 누적 10점 초과 시 자동 영업 정지
                penalty_suspended = CASE WHEN penalty_score + :point >= 10 THEN true ELSE penalty_suspended END,
                is_available      = CASE WHEN penalty_score + :point >= 10 THEN false ELSE is_available END
            WHERE id = :shop_id
        """),
        {"point": penalty_point, "shop_id": shop_id},
    )


@router.post("/{order_id}/reject")
async def reject_order(
    order_id: UUID,
    req: RejectOrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("PARTNER")),
):
    """
    점주 주문 거절 — PENDING 상태만 가능.
    거절 시 패널티 1점 부과, 누적 10점 시 자동 영업 정지.
    """
    # PENDING 주문은 아직 shop_id=NULL 이므로 orders 테이블만 조회
    # 점주 본인의 shop_id는 current_user.shop_id 사용
    if not current_user.shop_id:
        raise HTTPException(400, "등록된 매장이 없습니다")

    result = await db.execute(
        text("""
            SELECT o.id, o.status::text, o.customer_id,
                   o.ordered_at, u.fcm_token
            FROM orders o
            JOIN users u ON u.id = o.customer_id
            WHERE o.id = :oid
        """),
        {"oid": order_id},
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")
    if order.status != "PENDING":
        raise HTTPException(400, "대기 중인 주문만 거절할 수 있습니다")

    await db.execute(
        text("""
            UPDATE orders
            SET rejected_at = NOW(), reject_reason = :reason, updated_at = NOW()
            WHERE id = :id
        """),
        {"reason": req.reason or "점주 거절", "id": order_id},
    )

    shop_id_str = str(current_user.shop_id)

    # 패널티: 거절 1점
    await _record_penalty(
        db, shop_id_str, order_id,
        penalty_type="REJECTION",
        penalty_point=1,
        description=f"주문 거절: {req.reason or '사유 없음'}",
    )

    # 수락 지연 패널티 추가 확인 (30분 초과 시 LATE_ACCEPT 1점 추가)
    from datetime import datetime as dt, timezone as tz
    ordered_at = order.ordered_at
    if ordered_at.tzinfo is None:
        ordered_at = ordered_at.replace(tzinfo=tz.utc)
    elapsed_min = (dt.now(tz.utc) - ordered_at).total_seconds() / 60
    if elapsed_min > 30:
        await _record_penalty(
            db, shop_id_str, order_id,
            penalty_type="LATE_ACCEPT",
            penalty_point=1,
            description=f"수락 지연 {int(elapsed_min)}분 후 거절",
        )

    await db.commit()

    # 고객에게 알림
    asyncio.create_task(
        send_customer_status_notification(
            str(order.customer_id), order.fcm_token, str(order_id),
            "주문 거절 ❌", "다른 점주가 배정될 예정입니다. 잠시 기다려 주세요.",
        )
    )

    return {"success": True, "message": "주문이 거절되었습니다"}


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
