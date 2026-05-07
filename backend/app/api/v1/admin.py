"""
관리자 API — FastAPI
────────────────────
GET  /api/v1/admin/dashboard     KPI 요약
GET  /api/v1/admin/orders        주문 관제 (페이지네이션)
GET  /api/v1/admin/shops         점포 현황
GET  /api/v1/admin/sla-at-risk   SLA 위험 주문
GET  /api/v1/admin/settlements   정산 내역
GET  /api/v1/admin/audit-logs    접근 감사 로그

모든 엔드포인트: ADMIN 역할 필수 + 감사 로그 자동 기록
"""
from __future__ import annotations
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user, require_role

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


@router.get("/sla-at-risk")
async def get_sla_at_risk(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    rows = await db.execute(text("SELECT * FROM vw_sla_at_risk ORDER BY hours_left"))
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
