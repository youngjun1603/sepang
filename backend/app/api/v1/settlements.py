"""
정산 API
────────
GET  /api/v1/settlements/          점주 정산 목록
GET  /api/v1/settlements/{id}      정산 상세
"""
from uuid import UUID
from typing import Optional, List
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_user, require_role

router = APIRouter(prefix="/settlements", tags=["settlements"])


class SettlementOut(BaseModel):
    id:           str
    shop_id:      str
    period_start: date
    period_end:   date
    order_count:  int
    total_sales:  int
    platform_fee: int
    net_payout:   int
    payout_date:  Optional[date]
    status:       str


@router.get("/", response_model=List[SettlementOut])
async def list_settlements(
    shop_id: Optional[UUID] = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 파트너는 자신의 샵만, 관리자는 모든 샵 조회 가능
    if current_user.role == "PARTNER":
        result = await db.execute(
            text("""
                SELECT s.id, s.shop_id, s.period_start, s.period_end,
                       s.order_count, s.total_sales, s.platform_fee, s.net_payout,
                       s.payout_date, s.status
                FROM settlements s
                JOIN shops sh ON sh.id = s.shop_id
                WHERE sh.owner_id = :owner_id
                ORDER BY s.period_start DESC
                LIMIT 24
            """),
            {"owner_id": current_user.id},
        )
    elif current_user.role == "ADMIN":
        query = "SELECT id, shop_id, period_start, period_end, order_count, total_sales, platform_fee, net_payout, payout_date, status FROM settlements"
        params: dict = {}
        if shop_id:
            query += " WHERE shop_id = :shop_id"
            params["shop_id"] = shop_id
        query += " ORDER BY period_start DESC LIMIT 100"
        result = await db.execute(text(query), params)
    else:
        raise HTTPException(403, "접근 권한이 없습니다")

    rows = result.mappings().all()
    return [
        {**dict(r), "id": str(r["id"]), "shop_id": str(r["shop_id"])}
        for r in rows
    ]


@router.get("/{settlement_id}", response_model=SettlementOut)
async def get_settlement(
    settlement_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("""
            SELECT s.id, s.shop_id, s.period_start, s.period_end,
                   s.order_count, s.total_sales, s.platform_fee, s.net_payout,
                   s.payout_date, s.status
            FROM settlements s
            WHERE s.id = :id
        """),
        {"id": settlement_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "정산 내역을 찾을 수 없습니다")
    return {**dict(row._mapping), "id": str(row.id), "shop_id": str(row.shop_id)}
