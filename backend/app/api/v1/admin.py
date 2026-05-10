"""
관리자 API — FastAPI
────────────────────
GET  /api/v1/admin/dashboard     KPI 요약
GET  /api/v1/admin/orders        주문 관제 (페이지네이션)
GET  /api/v1/admin/shops         점포 현황
POST /api/v1/admin/shops         점포 등록 (파트너 계정 동시 생성)
GET  /api/v1/admin/sla-at-risk   SLA 위험 주문
GET  /api/v1/admin/settlements   정산 내역
GET  /api/v1/admin/audit-logs    접근 감사 로그

모든 엔드포인트: ADMIN 역할 필수 + 감사 로그 자동 기록
"""
from __future__ import annotations
from typing import Optional
from datetime import date
from uuid import UUID

import bcrypt
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.auth import get_current_user, require_role
from app.core.config import settings
from app.services.geocoding import geocode_address
from app.api.v1.orders import _do_cancel_order, ADMIN_NON_CANCELLABLE

_bearer = HTTPBearer(auto_error=False)


async def _monitor_or_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials if credentials else None
    if settings.MONITOR_API_TOKEN and token == settings.MONITOR_API_TOKEN:
        class _MonitorUser:
            id = "monitor"
            role = "ADMIN"
        return _MonitorUser()
    return await require_role("ADMIN")(await get_current_user(credentials))

router = APIRouter(prefix="/admin", tags=["admin"])


# ── 감사 로그 기록 헬퍼 ───────────────────────────────────────────────────────

async def _audit(db: AsyncSession, request: Request, current_user, action: str):
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    await db.execute(
        text("""
            INSERT INTO admin_audit_logs (admin_id, ip_address, path, action)
            VALUES (:aid, :ip, :path, :action)
        """),
        {"aid": current_user.id, "ip": client_ip, "path": request.url.path, "action": action},
    )
    await db.commit()


# ── Schemas ────────────────────────────────────────────────────────────────────

class DashboardKpi(BaseModel):
    today_orders: int
    conversion_rate: float
    avg_order_value: int
    sla_violations: int
    week_revenue: int
    active_shops: int


class AdminOrder(BaseModel):
    id: str
    customer_name: str
    shop_name: Optional[str]
    service_type: str
    status: str
    total_amount: int
    hours_left: Optional[float]
    ordered_at: str


class AdminShop(BaseModel):
    id: str
    name: str
    region: str
    team_type: str
    today_orders: int
    rating: float
    is_active: bool
    is_available: bool


class AdminSettlement(BaseModel):
    id: str
    shop_name: str
    period_start: str
    period_end: str
    order_count: int
    total_sales: int
    platform_fee: int
    net_payout: int
    payout_date: Optional[str]
    status: str


class AuditLog(BaseModel):
    id: int
    admin_email: str
    ip_address: str
    path: str
    action: str
    created_at: str


class PaginatedOrders(BaseModel):
    items: list[AdminOrder]
    total: int
    page: int
    pages: int


class CreateShopRequest(BaseModel):
    name:            str   = Field(..., min_length=2, max_length=100)
    address:         str   = Field(..., min_length=5)
    owner_name:      str   = Field(..., min_length=2, max_length=50)
    phone:           str   = Field(..., pattern=r"^010\d{8}$")
    business_number: str   = Field(..., pattern=r"^\d{3}-\d{2}-\d{5}$")
    password:        str   = Field(..., min_length=8)
    team_type:       str   = Field("DAY", pattern=r"^(DAY|NIGHT|BOTH)$")
    radius_km:       float = Field(3.0, ge=1, le=20)
    bank_name:       Optional[str] = None
    bank_account:    Optional[str] = None
    bank_holder:     Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardKpi)
async def get_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    row = await db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM orders WHERE ordered_at::date = CURRENT_DATE)                          AS today_orders,
            (SELECT COUNT(*) FROM orders WHERE ordered_at::date = CURRENT_DATE AND status = 'COMPLETED') AS today_completed,
            (SELECT ROUND(AVG(total_amount)::numeric, 0)
               FROM orders WHERE ordered_at >= NOW() - INTERVAL '7 days' AND status = 'COMPLETED')      AS avg_order_value,
            (SELECT COUNT(*) FROM orders
               WHERE deadline_at < NOW() AND status NOT IN ('COMPLETED','CANCELLED'))                    AS sla_violations,
            (SELECT COALESCE(SUM(total_amount), 0)
               FROM orders WHERE ordered_at >= NOW() - INTERVAL '7 days' AND status = 'COMPLETED')      AS week_revenue,
            (SELECT COUNT(*) FROM shops WHERE is_active AND is_available)                                AS active_shops
    """))
    r = row.fetchone()

    today_orders = r.today_orders or 0
    today_completed = r.today_completed or 0
    conversion_rate = round(today_completed / today_orders * 100, 1) if today_orders > 0 else 0.0

    await _audit(db, request, current_user, "대시보드 조회")
    return DashboardKpi(
        today_orders=today_orders,
        conversion_rate=conversion_rate,
        avg_order_value=int(r.avg_order_value or 0),
        sla_violations=r.sla_violations or 0,
        week_revenue=int(r.week_revenue or 0),
        active_shops=r.active_shops or 0,
    )


@router.get("/orders", response_model=PaginatedOrders)
async def list_orders(
    request: Request,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    where = "WHERE 1=1"
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if status:
        where += " AND o.status = CAST(:status AS order_status)"
        params["status"] = status

    rows = await db.execute(text(f"""
        SELECT
            o.id::text, u.name AS customer_name,
            s.name AS shop_name, o.service_type::text, o.status::text,
            o.total_amount,
            ROUND(EXTRACT(EPOCH FROM (o.deadline_at - NOW())) / 3600, 1) AS hours_left,
            o.ordered_at::text
        FROM orders o
        JOIN users u ON u.id = o.customer_id
        LEFT JOIN shops s ON s.id = o.shop_id
        {where}
        ORDER BY o.ordered_at DESC
        LIMIT :limit OFFSET :offset
    """), params)

    count_row = await db.execute(text(f"""
        SELECT COUNT(*) FROM orders o {where}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")})

    total = count_row.scalar() or 0
    items = [
        AdminOrder(
            id=r.id, customer_name=r.customer_name, shop_name=r.shop_name,
            service_type=r.service_type, status=r.status,
            total_amount=r.total_amount, hours_left=r.hours_left,
            ordered_at=r.ordered_at,
        )
        for r in rows.fetchall()
    ]

    await _audit(db, request, current_user, "주문 목록 조회")
    return PaginatedOrders(items=items, total=total, page=page, pages=max(1, -(-total // page_size)))


class ForceCancelRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=200)


@router.post("/orders/{order_id}/force-cancel")
async def force_cancel_order(
    order_id: UUID,
    body:     ForceCancelRequest,
    request:  Request,
    db:       AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    """관리자 강제 취소 — 어떤 진행 상태든 취소 가능 (완료·취소 제외)"""
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
    if order.status in ADMIN_NON_CANCELLABLE:
        raise HTTPException(400, f"이미 {order.status} 상태의 주문은 취소할 수 없습니다")

    await _do_cancel_order(db, order, f"[관리자 강제취소] {body.reason}")
    await _audit(db, request, current_user, f"주문 강제취소: {order_id} — {body.reason}")
    return {"success": True}


@router.get("/shops", response_model=list[AdminShop])
async def list_shops(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    rows = await db.execute(text("""
        SELECT
            s.id::text, s.name,
            COALESCE(SPLIT_PART(s.address, ' ', 2), s.address) AS region,
            s.team_type::text, s.rating, s.is_active, s.is_available,
            COUNT(o.id) FILTER (WHERE o.ordered_at::date = CURRENT_DATE) AS today_orders
        FROM shops s
        LEFT JOIN orders o ON o.shop_id = s.id
        GROUP BY s.id
        ORDER BY today_orders DESC, s.name
    """))

    await _audit(db, request, current_user, "점포 목록 조회")
    return [
        AdminShop(
            id=r.id, name=r.name, region=r.region,
            team_type=r.team_type, today_orders=r.today_orders or 0,
            rating=float(r.rating or 0), is_active=r.is_active, is_available=r.is_available,
        )
        for r in rows.fetchall()
    ]


@router.post("/shops", status_code=201)
async def create_shop(
    request: Request,
    body: CreateShopRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    # 중복 사업자번호 확인
    dup = await db.execute(
        text("SELECT id FROM users WHERE business_number = :bn"),
        {"bn": body.business_number},
    )
    if dup.fetchone():
        raise HTTPException(409, f"이미 등록된 사업자번호입니다: {body.business_number}")

    # 주소 → 좌표 (Kakao 미설정 시 서울 중심 fallback)
    geo = await geocode_address(body.address)
    lat = geo.lat if geo else 37.5665
    lng = geo.lng if geo else 126.9780

    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    user_row = await db.execute(
        text("""
            INSERT INTO users (role, name, phone, business_number, password_hash)
            VALUES ('PARTNER', :name, :phone, :bn, :pw)
            RETURNING id
        """),
        {"name": body.owner_name, "phone": body.phone, "bn": body.business_number, "pw": pw_hash},
    )
    user_id = user_row.scalar()

    shop_row = await db.execute(
        text("""
            INSERT INTO shops (
                owner_id, name, address, location,
                team_type, radius_km,
                bank_name, bank_account, bank_holder
            ) VALUES (
                :owner_id, :name, :address,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                CAST(:team_type AS team_type), :radius,
                :bank_name, :bank_account, :bank_holder
            )
            RETURNING id
        """),
        {
            "owner_id": user_id,
            "name": body.name,
            "address": body.address,
            "lat": lat, "lng": lng,
            "team_type": body.team_type,
            "radius": body.radius_km,
            "bank_name": body.bank_name,
            "bank_account": body.bank_account,
            "bank_holder": body.bank_holder,
        },
    )
    shop_id = shop_row.scalar()

    await db.commit()
    await _audit(db, request, current_user, f"점포 등록: {body.name} ({body.business_number})")
    return {"id": str(shop_id), "name": body.name, "lat": lat, "lng": lng}


@router.get("/sla-at-risk")
async def get_sla_at_risk(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(_monitor_or_admin),
):
    rows = await db.execute(text("""
        SELECT
            o.id::text          AS id,
            u.name              AS customer_name,
            u.phone             AS customer_phone,
            s.name              AS shop_name,
            o.status::text      AS status,
            o.deadline_at::text AS deadline_at,
            ROUND(EXTRACT(EPOCH FROM (o.deadline_at - NOW())) / 3600, 1) AS hours_left
        FROM orders o
        JOIN users u ON u.id = o.customer_id
        LEFT JOIN shops s ON s.id = o.shop_id
        WHERE o.status NOT IN ('COMPLETED', 'CANCELLED')
          AND o.deadline_at < NOW() + INTERVAL '4 hours'
        ORDER BY o.deadline_at
    """))
    if getattr(current_user, "id", None) != "monitor":
        await _audit(db, request, current_user, "SLA 위험 주문 조회")
    return [dict(r._mapping) for r in rows.fetchall()]


@router.get("/settlements", response_model=list[AdminSettlement])
async def list_settlements(
    request: Request,
    period_start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    where = "WHERE 1=1"
    params: dict = {}
    if period_start:
        where += " AND ws.period_start >= CAST(:period_start AS date)"
        params["period_start"] = period_start

    rows = await db.execute(text(f"""
        SELECT
            ws.id::text, s.name AS shop_name,
            ws.period_start::text, ws.period_end::text,
            ws.order_count, ws.total_sales, ws.platform_fee, ws.net_payout,
            ws.payout_date::text, ws.status::text
        FROM settlements ws
        JOIN shops s ON s.id = ws.shop_id
        {where}
        ORDER BY ws.period_start DESC, s.name
    """), params)

    await _audit(db, request, current_user, "정산 목록 조회")
    return [
        AdminSettlement(
            id=r.id, shop_name=r.shop_name,
            period_start=r.period_start, period_end=r.period_end,
            order_count=r.order_count, total_sales=r.total_sales,
            platform_fee=r.platform_fee, net_payout=r.net_payout,
            payout_date=r.payout_date, status=r.status,
        )
        for r in rows.fetchall()
    ]


@router.patch("/settlements/{settlement_id}/pay")
async def mark_settlement_paid(
    settlement_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    result = await db.execute(
        text("""
            UPDATE settlements
            SET status = 'PAID', payout_date = CURRENT_DATE
            WHERE id = :id AND status = 'PENDING'
            RETURNING id
        """),
        {"id": settlement_id},
    )
    if not result.fetchone():
        raise HTTPException(404, "정산 내역을 찾을 수 없거나 이미 지급 완료 상태입니다")
    await db.commit()
    await _audit(db, request, current_user, f"정산 지급 처리: {settlement_id}")
    return {"success": True}


@router.get("/marketing")
async def get_marketing_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    r = (await db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM users WHERE role = 'CUSTOMER')                                         AS total_customers,
            (SELECT COUNT(*) FROM users WHERE role = 'CUSTOMER' AND created_at::date = CURRENT_DATE)     AS new_today,
            (SELECT COUNT(*) FROM users WHERE role = 'CUSTOMER' AND created_at >= NOW() - INTERVAL '7 days') AS new_week,
            (SELECT COUNT(*) FROM users WHERE role = 'CUSTOMER' AND fcm_token IS NOT NULL)               AS fcm_opt_in,
            (SELECT COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0) FROM point_transactions)         AS points_issued,
            (SELECT COALESCE(SUM(ABS(amount)) FILTER (WHERE amount < 0), 0) FROM point_transactions)    AS points_redeemed
    """))).fetchone()

    coupon_rows = await db.execute(text("""
        SELECT c.code, c.name,
               COUNT(uc.id) FILTER (WHERE uc.used_at IS NOT NULL) AS used_count,
               COUNT(uc.id) AS issued_count
        FROM coupons c
        LEFT JOIN user_coupons uc ON uc.coupon_id = c.id
        GROUP BY c.id, c.code, c.name
        ORDER BY used_count DESC
    """))
    coupons = [
        {"code": row.code, "name": row.name, "used_count": int(row.used_count), "issued_count": int(row.issued_count)}
        for row in coupon_rows.fetchall()
    ]

    d3_target = (await db.execute(text("""
        SELECT COUNT(*) FROM users u
        WHERE u.role = 'CUSTOMER'
          AND u.fcm_token IS NOT NULL
          AND u.created_at <= NOW() - INTERVAL '3 days'
          AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = u.id)
    """))).scalar() or 0

    night_target = (await db.execute(text("""
        SELECT COUNT(DISTINCT u.id) FROM users u
        JOIN orders o ON o.customer_id = u.id
        WHERE u.role = 'CUSTOMER'
          AND u.fcm_token IS NOT NULL
          AND o.service_type = 'NIGHT'
    """))).scalar() or 0

    await _audit(db, request, current_user, "마케팅 현황 조회")
    return {
        "total_customers": int(r.total_customers or 0),
        "new_today":       int(r.new_today or 0),
        "new_week":        int(r.new_week or 0),
        "fcm_opt_in":      int(r.fcm_opt_in or 0),
        "points_issued":   int(r.points_issued or 0),
        "points_redeemed": int(r.points_redeemed or 0),
        "coupons":         coupons,
        "d3_target":       int(d3_target),
        "night_target":    int(night_target),
    }


@router.get("/audit-logs", response_model=list[AuditLog])
async def get_audit_logs(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    rows = await db.execute(text("""
        SELECT al.id, u.email AS admin_email,
               al.ip_address, al.path, al.action, al.created_at::text
        FROM admin_audit_logs al
        JOIN users u ON u.id = al.admin_id
        ORDER BY al.created_at DESC
        LIMIT :limit
    """), {"limit": limit})

    await _audit(db, request, current_user, "감사 로그 조회")
    return [
        AuditLog(
            id=r.id, admin_email=r.admin_email, ip_address=r.ip_address,
            path=r.path, action=r.action, created_at=r.created_at,
        )
        for r in rows.fetchall()
    ]
