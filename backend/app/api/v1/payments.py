"""
결제 API — 토스페이먼츠
──────────────────────
POST /api/v1/payments/prepare      결제 준비 (clientKey + amount 반환)
POST /api/v1/payments/confirm      결제 승인 (paymentKey, orderId, amount)
POST /api/v1/payments/{order_id}/cancel  결제 취소/환불
GET  /api/v1/payments/{order_id}   결제 상태 조회
"""
import base64
import json
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.config import settings

router = APIRouter(prefix="/payments", tags=["payments"])

TOSS_API_BASE = "https://api.tosspayments.com/v1/payments"


def _toss_auth_header() -> dict:
    """시크릿 키를 Basic 인증 헤더로 변환"""
    encoded = base64.b64encode(f"{settings.TOSS_SECRET_KEY}:".encode()).decode()
    return {"Authorization": f"Basic {encoded}", "Content-Type": "application/json"}


# ── Schemas ──────────────────────────────────────────────────────────────────

class PrepareResponse(BaseModel):
    client_key:   str
    order_id:     str
    amount:       int
    order_name:   str

class ConfirmRequest(BaseModel):
    payment_key:  str
    order_id:     str
    amount:       int

class CancelRequest(BaseModel):
    cancel_reason: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/prepare/{order_id}", response_model=PrepareResponse)
async def prepare_payment(
    order_id:     UUID,
    db:           AsyncSession = Depends(get_db),
    current_user  = Depends(require_role("CUSTOMER")),
):
    """
    결제 준비 — 프론트엔드에 clientKey와 주문 정보 반환.
    토스페이먼츠 위젯 초기화에 사용.
    """
    if not settings.TOSS_CLIENT_KEY:
        raise HTTPException(503, "결제 서비스가 설정되지 않았습니다")

    result = await db.execute(
        text("""
            SELECT id, wash_category, total_amount, payment_status, customer_id
            FROM orders WHERE id = :id
        """),
        {"id": order_id},
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")
    if str(order.customer_id) != str(current_user.id):
        raise HTTPException(403, "본인 주문만 결제할 수 있습니다")
    if order.payment_status == "PAID":
        raise HTTPException(400, "이미 결제 완료된 주문입니다")

    label_row = await db.execute(
        text("SELECT label FROM wash_items WHERE key = :key LIMIT 1"),
        {"key": order.wash_category},
    )
    label_rec = label_row.fetchone()
    label = label_rec.label if label_rec else "세탁 서비스"

    return PrepareResponse(
        client_key=settings.TOSS_CLIENT_KEY,
        order_id=str(order.id),
        amount=order.total_amount,
        order_name=f"세팡 {label}",
    )


@router.post("/confirm")
async def confirm_payment(
    req:          ConfirmRequest,
    db:           AsyncSession = Depends(get_db),
    current_user  = Depends(require_role("CUSTOMER")),
):
    """
    결제 승인 — 토스페이먼츠 서버에 최종 승인 요청.
    프론트엔드 결제 완료 콜백에서 호출.
    """
    if not settings.TOSS_SECRET_KEY:
        raise HTTPException(503, "결제 서비스가 설정되지 않았습니다")

    # 주문 검증
    result = await db.execute(
        text("SELECT id, total_amount, payment_status, customer_id FROM orders WHERE id = :id"),
        {"id": req.order_id},
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")
    if str(order.customer_id) != str(current_user.id):
        raise HTTPException(403, "본인 주문만 결제할 수 있습니다")
    if order.payment_status == "PAID":
        raise HTTPException(400, "이미 결제 완료된 주문입니다")
    if order.total_amount != req.amount:
        raise HTTPException(400, f"결제 금액이 일치하지 않습니다 (주문: {order.total_amount}원)")

    # 토스페이먼츠 승인 요청
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{TOSS_API_BASE}/confirm",
            headers=_toss_auth_header(),
            json={
                "paymentKey": req.payment_key,
                "orderId":    req.order_id,
                "amount":     req.amount,
            },
        )

    toss_data = resp.json()

    if resp.status_code != 200:
        error_msg = toss_data.get("message", "결제 승인에 실패했습니다")
        # 실패 트랜잭션 기록
        await db.execute(
            text("""
                INSERT INTO payment_transactions (id, order_id, amount, status, toss_response)
                VALUES (:key, :oid, :amt, 'FAILED', :raw)
                ON CONFLICT (id) DO NOTHING
            """),
            {"key": req.payment_key, "oid": req.order_id,
             "amt": req.amount, "raw": json.dumps(toss_data)},
        )
        await db.commit()
        raise HTTPException(400, error_msg)

    method = toss_data.get("method", "")

    # orders 업데이트
    await db.execute(
        text("""
            UPDATE orders
            SET payment_status = 'PAID',
                payment_key    = :key,
                payment_method = :method,
                paid_at        = NOW(),
                updated_at     = NOW()
            WHERE id = :oid
        """),
        {"key": req.payment_key, "method": method, "oid": req.order_id},
    )

    # 트랜잭션 기록
    await db.execute(
        text("""
            INSERT INTO payment_transactions (id, order_id, amount, status, method, toss_response)
            VALUES (:key, :oid, :amt, 'PAID', :method, :raw)
            ON CONFLICT (id) DO UPDATE SET status = 'PAID', updated_at = NOW()
        """),
        {"key": req.payment_key, "oid": req.order_id, "amt": req.amount,
         "method": method, "raw": json.dumps(toss_data)},
    )
    await db.commit()

    return {
        "success":        True,
        "payment_key":    req.payment_key,
        "method":         method,
        "approved_at":    toss_data.get("approvedAt"),
        "receipt_url":    toss_data.get("receipt", {}).get("url"),
    }


@router.post("/{order_id}/cancel")
async def cancel_payment(
    order_id:     UUID,
    req:          CancelRequest,
    db:           AsyncSession = Depends(get_db),
    current_user  = Depends(get_current_user),
):
    """
    결제 취소/환불.
    - 고객: 수거 전(PENDING·ACCEPTED) 상태만 가능
    - 관리자: 모든 주문 가능
    쿠폰·포인트 자동 복원 + 점주 알림 포함
    """
    result = await db.execute(
        text("""
            SELECT id, payment_key, payment_status, customer_id, total_amount,
                   status::text AS order_status, coupon_id, points_used, shop_id
            FROM orders WHERE id = :id
        """),
        {"id": order_id},
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")

    is_admin = current_user.role == "ADMIN"
    is_owner = str(order.customer_id) == str(current_user.id)
    if not is_admin and not is_owner:
        raise HTTPException(403, "권한이 없습니다")

    # 고객은 점주 수락 전(PENDING)만 취소 가능, 점주는 ACCEPTED·PICKED_UP 취소 가능
    if not is_admin:
        if is_owner and order.order_status not in {"PENDING"}:
            raise HTTPException(400, "점주가 수락하기 전 주문만 취소할 수 있습니다. 취소가 필요하면 점주에게 직접 연락해 주세요.")
        if not is_owner:
            raise HTTPException(403, "권한이 없습니다")

    if order.payment_status != "PAID":
        raise HTTPException(400, "결제 완료 상태의 주문만 취소할 수 있습니다")
    if not order.payment_key:
        raise HTTPException(400, "결제 키가 없습니다")

    # ── 1. 토스페이먼츠 환불 요청 ──────────────────────────────
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{TOSS_API_BASE}/{order.payment_key}/cancel",
            headers=_toss_auth_header(),
            json={"cancelReason": req.cancel_reason},
        )

    toss_data = resp.json()
    if resp.status_code != 200:
        raise HTTPException(400, toss_data.get("message", "결제 취소에 실패했습니다"))

    # ── 2. 주문 상태 업데이트 ──────────────────────────────────
    await db.execute(
        text("""
            UPDATE orders
            SET payment_status = 'REFUNDED',
                status         = 'CANCELLED',
                cancelled_at   = NOW(),
                cancel_reason  = :reason,
                updated_at     = NOW()
            WHERE id = :oid
        """),
        {"reason": req.cancel_reason, "oid": order_id},
    )
    await db.execute(
        text("""
            UPDATE payment_transactions
            SET status = 'REFUNDED', cancel_reason = :reason, updated_at = NOW()
            WHERE order_id = :oid
        """),
        {"reason": req.cancel_reason, "oid": order_id},
    )

    # ── 3. 쿠폰 복원 ──────────────────────────────────────────
    if order.coupon_id:
        await db.execute(
            text("""
                UPDATE user_coupons
                SET used_at = NULL, order_id = NULL
                WHERE coupon_id = :cid AND user_id = :uid
            """),
            {"cid": order.coupon_id, "uid": order.customer_id},
        )

    # ── 4. 포인트 복원 ────────────────────────────────────────
    points_used = order.points_used or 0
    if points_used > 0:
        bal_row = await db.execute(
            text("""
                SELECT COALESCE(balance, 0) FROM point_transactions
                WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1
            """),
            {"uid": order.customer_id},
        )
        cur_bal = (bal_row.fetchone() or (0,))[0]
        await db.execute(
            text("""
                INSERT INTO point_transactions (user_id, amount, balance, reason, order_id)
                VALUES (:uid, :amt, :bal, '결제 취소 포인트 환불', :oid)
            """),
            {
                "uid": order.customer_id,
                "amt": points_used,
                "bal": cur_bal + points_used,
                "oid": order_id,
            },
        )

    await db.commit()

    # ── 5. 알림 전송 (비동기) ─────────────────────────────────
    import asyncio
    from app.services.notification import send_customer_status_notification

    notif_row = await db.execute(
        text("""
            SELECT cu.fcm_token AS customer_fcm, cu.id::text AS customer_id,
                   pu.fcm_token AS partner_fcm,  pu.id::text AS partner_id
            FROM orders o
            JOIN users cu ON cu.id = o.customer_id
            LEFT JOIN shops sh ON sh.id = o.shop_id
            LEFT JOIN users pu ON pu.id = sh.owner_id
            WHERE o.id = :oid
        """),
        {"oid": order_id},
    )
    notif = notif_row.fetchone()
    if notif:
        asyncio.create_task(
            send_customer_status_notification(
                notif.customer_id, notif.customer_fcm, str(order_id),
                "결제 취소 완료 ✅", "결제가 취소되고 환불이 진행됩니다.",
            )
        )
        if notif.partner_fcm:
            asyncio.create_task(
                send_customer_status_notification(
                    notif.partner_id, notif.partner_fcm, str(order_id),
                    "담당 주문 취소 ❌", f"고객이 결제를 취소했습니다. ({req.cancel_reason})",
                )
            )

    return {
        "success":       True,
        "status":        "REFUNDED",
        "coupon_restored":  bool(order.coupon_id),
        "points_restored":  points_used,
    }


@router.get("/{order_id}")
async def get_payment_status(
    order_id:    UUID,
    db:          AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """결제 상태 조회"""
    result = await db.execute(
        text("""
            SELECT o.id, o.total_amount, o.payment_status, o.payment_method,
                   o.payment_key, o.paid_at, o.customer_id
            FROM orders o
            WHERE o.id = :id
        """),
        {"id": order_id},
    )
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "주문을 찾을 수 없습니다")

    is_admin = current_user.role == "ADMIN"
    is_owner = str(order.customer_id) == str(current_user.id)
    if not is_admin and not is_owner:
        raise HTTPException(403, "권한이 없습니다")

    return {
        "order_id":       str(order.id),
        "amount":         order.total_amount,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "paid_at":        order.paid_at,
    }
