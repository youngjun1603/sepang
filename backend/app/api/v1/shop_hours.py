"""
매장 운영 시간 API
──────────────────
GET  /api/v1/shops/hours           내 매장 운영 시간 조회 (점주)
PUT  /api/v1/shops/hours           내 매장 운영 시간 일괄 저장 (점주)
GET  /api/v1/shops/{shop_id}/hours 특정 매장 운영 시간 조회 (공개)
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field, model_validator

from app.core.database import get_db
from app.core.auth import get_current_user, require_role

router = APIRouter(tags=["shop-hours"])

DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]


# ── Schemas ────────────────────────────────────────────────────────

class ShopHourItem(BaseModel):
    day_of_week: int     = Field(..., ge=0, le=6)
    is_closed:   bool    = False
    is_24h:      bool    = False
    open_time:   Optional[str] = None   # "HH:MM"
    close_time:  Optional[str] = None   # "HH:MM"

    @model_validator(mode="after")
    def validate_times(self):
        if self.is_closed or self.is_24h:
            return self
        if not self.open_time or not self.close_time:
            raise ValueError("영업 시간(open_time, close_time)을 입력해 주세요")
        return self

class ShopHoursRequest(BaseModel):
    hours: list[ShopHourItem] = Field(..., min_length=7, max_length=7)

class ShopHourOut(BaseModel):
    day_of_week: int
    day_name:    str
    is_closed:   bool
    is_24h:      bool
    open_time:   Optional[str]
    close_time:  Optional[str]


# ── Helpers ────────────────────────────────────────────────────────

def _row_to_out(row) -> dict:
    return {
        "day_of_week": row.day_of_week,
        "day_name":    DAY_NAMES[row.day_of_week],
        "is_closed":   row.is_closed,
        "is_24h":      row.is_24h,
        "open_time":   str(row.open_time)[:5] if row.open_time else None,
        "close_time":  str(row.close_time)[:5] if row.close_time else None,
    }


async def _default_hours(shop_id: str) -> list[dict]:
    """운영 시간 미설정 시 기본값 (24h 영업 7일)"""
    return [
        {
            "day_of_week": d,
            "day_name":    DAY_NAMES[d],
            "is_closed":   False,
            "is_24h":      True,
            "open_time":   None,
            "close_time":  None,
        }
        for d in range(7)
    ]


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/shops/hours", response_model=list[ShopHourOut])
async def get_my_shop_hours(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("PARTNER")),
):
    """점주 본인 매장의 운영 시간 조회"""
    shop_id = current_user.shop_id
    if not shop_id:
        raise HTTPException(404, "등록된 매장이 없습니다")

    result = await db.execute(
        text("""
            SELECT day_of_week, is_closed, is_24h, open_time, close_time
            FROM shop_hours
            WHERE shop_id = :shop_id
            ORDER BY day_of_week
        """),
        {"shop_id": shop_id},
    )
    rows = result.fetchall()

    if not rows:
        return await _default_hours(shop_id)

    # 누락된 요일 기본값(24h)으로 채우기
    existing = {r.day_of_week: r for r in rows}
    result_list = []
    for d in range(7):
        if d in existing:
            result_list.append(_row_to_out(existing[d]))
        else:
            result_list.append({
                "day_of_week": d, "day_name": DAY_NAMES[d],
                "is_closed": False, "is_24h": True,
                "open_time": None, "close_time": None,
            })
    return result_list


@router.put("/shops/hours")
async def update_my_shop_hours(
    req: ShopHoursRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("PARTNER")),
):
    """점주 본인 매장 운영 시간 일괄 저장 (7일 전체)"""
    shop_id = current_user.shop_id
    if not shop_id:
        raise HTTPException(404, "등록된 매장이 없습니다")

    days_provided = sorted(h.day_of_week for h in req.hours)
    if days_provided != list(range(7)):
        raise HTTPException(400, "요일 0~6 (월~일) 7개를 모두 입력해 주세요")

    for item in req.hours:
        await db.execute(
            text("""
                INSERT INTO shop_hours (shop_id, day_of_week, is_closed, is_24h, open_time, close_time)
                VALUES (:shop_id, :dow, :closed, :all_day, :open, :close)
                ON CONFLICT (shop_id, day_of_week) DO UPDATE
                    SET is_closed  = EXCLUDED.is_closed,
                        is_24h     = EXCLUDED.is_24h,
                        open_time  = EXCLUDED.open_time,
                        close_time = EXCLUDED.close_time
            """),
            {
                "shop_id": shop_id,
                "dow":     item.day_of_week,
                "closed":  item.is_closed,
                "all_day": item.is_24h,
                "open":    item.open_time,
                "close":   item.close_time,
            },
        )

    await db.commit()
    return {"success": True, "message": "운영 시간이 저장되었습니다"}


@router.get("/shops/{shop_id}/hours", response_model=list[ShopHourOut])
async def get_shop_hours_public(
    shop_id: str,
    db: AsyncSession = Depends(get_db),
):
    """특정 매장 운영 시간 공개 조회"""
    result = await db.execute(
        text("""
            SELECT day_of_week, is_closed, is_24h, open_time, close_time
            FROM shop_hours
            WHERE shop_id = :shop_id
            ORDER BY day_of_week
        """),
        {"shop_id": shop_id},
    )
    rows = result.fetchall()
    if not rows:
        return await _default_hours(shop_id)

    existing = {r.day_of_week: r for r in rows}
    result_list = []
    for d in range(7):
        if d in existing:
            result_list.append(_row_to_out(existing[d]))
        else:
            result_list.append({
                "day_of_week": d, "day_name": DAY_NAMES[d],
                "is_closed": False, "is_24h": True,
                "open_time": None, "close_time": None,
            })
    return result_list


async def is_shop_open(db: AsyncSession, shop_id: str) -> bool:
    """현재 시각 기준 매장 운영 중 여부 확인 (주문 생성 시 호출)"""
    from datetime import timezone, timedelta
    from datetime import datetime as dt

    now_kst = dt.now(timezone(timedelta(hours=9)))
    dow   = now_kst.weekday()          # 0=월 ... 6=일
    now_t = now_kst.strftime("%H:%M")  # "HH:MM"

    result = await db.execute(
        text("""
            SELECT is_closed, is_24h, open_time, close_time
            FROM shop_hours
            WHERE shop_id = :shop_id AND day_of_week = :dow
        """),
        {"shop_id": shop_id, "dow": dow},
    )
    row = result.fetchone()

    if not row:
        return True  # 설정 없으면 24h 영업으로 간주

    if row.is_closed:
        return False
    if row.is_24h:
        return True

    open_str  = str(row.open_time)[:5]   # "HH:MM"
    close_str = str(row.close_time)[:5]

    if close_str > open_str:
        return open_str <= now_t <= close_str
    else:
        # 자정을 넘기는 경우 (예: 22:00 ~ 02:00)
        return now_t >= open_str or now_t <= close_str
