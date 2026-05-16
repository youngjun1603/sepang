"""
요금 설정 API (관리자 전용)
────────────────────────────
GET  /api/v1/pricing/weather           날씨 요금 목록
PUT  /api/v1/pricing/weather/{id}      날씨 요금 수정
GET  /api/v1/pricing/distance          거리 구간 요금 목록
POST /api/v1/pricing/distance          거리 구간 추가
PUT  /api/v1/pricing/distance/{id}     거리 구간 수정
DELETE /api/v1/pricing/distance/{id}  거리 구간 삭제
GET  /api/v1/pricing/preview           요금 미리보기 (날씨+거리 조합)
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.auth import require_role

router = APIRouter(prefix="/pricing", tags=["pricing"])


# ── Schemas ────────────────────────────────────────────────────────

class WeatherPricingOut(BaseModel):
    id:          int
    condition:   str
    multiplier:  float
    is_active:   bool
    description: Optional[str]
    updated_at:  datetime

class WeatherPricingUpdate(BaseModel):
    multiplier:  float  = Field(..., ge=1.0, le=5.0)
    is_active:   bool   = True
    description: Optional[str] = None

class DistancePricingOut(BaseModel):
    id:          int
    min_km:      float
    max_km:      Optional[float]
    surcharge:   int
    is_active:   bool
    description: Optional[str]
    updated_at:  datetime

class DistancePricingCreate(BaseModel):
    min_km:      float  = Field(..., ge=0)
    max_km:      Optional[float] = Field(None, ge=0)
    surcharge:   int    = Field(..., ge=0)
    is_active:   bool   = True
    description: Optional[str] = None

class DistancePricingUpdate(BaseModel):
    min_km:      Optional[float] = Field(None, ge=0)
    max_km:      Optional[float] = Field(None, ge=0)
    surcharge:   Optional[int]   = Field(None, ge=0)
    is_active:   Optional[bool]  = None
    description: Optional[str]  = None

class PricePreviewRequest(BaseModel):
    base_amount:  int   = Field(..., ge=0)
    lat:          float = Field(..., ge=33, le=43)
    lon:          float = Field(..., ge=124, le=132)
    distance_km:  float = Field(..., ge=0)


# ── 날씨 요금 ─────────────────────────────────────────────────────

@router.get("/weather", response_model=list[WeatherPricingOut])
async def list_weather_pricing(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("ADMIN")),
):
    result = await db.execute(text("""
        SELECT id, condition, multiplier, is_active, description, updated_at
        FROM weather_pricing ORDER BY id
    """))
    return [dict(r._mapping) for r in result.fetchall()]


@router.put("/weather/{pricing_id}", response_model=WeatherPricingOut)
async def update_weather_pricing(
    pricing_id: int,
    req: WeatherPricingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    result = await db.execute(
        text("""
            UPDATE weather_pricing
            SET multiplier  = :mult,
                is_active   = :active,
                description = :desc,
                updated_at  = NOW(),
                updated_by  = :uid
            WHERE id = :id
            RETURNING id, condition, multiplier, is_active, description, updated_at
        """),
        {
            "mult":   req.multiplier,
            "active": req.is_active,
            "desc":   req.description,
            "uid":    current_user.id,
            "id":     pricing_id,
        },
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "날씨 요금 설정을 찾을 수 없습니다")
    await db.commit()
    return dict(row._mapping)


# ── 거리 구간 요금 ────────────────────────────────────────────────

@router.get("/distance", response_model=list[DistancePricingOut])
async def list_distance_pricing(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("ADMIN")),
):
    result = await db.execute(text("""
        SELECT id, min_km, max_km, surcharge, is_active, description, updated_at
        FROM distance_pricing ORDER BY min_km
    """))
    return [dict(r._mapping) for r in result.fetchall()]


@router.post("/distance", response_model=DistancePricingOut, status_code=201)
async def create_distance_pricing(
    req: DistancePricingCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    if req.max_km is not None and req.max_km <= req.min_km:
        raise HTTPException(400, "max_km은 min_km보다 커야 합니다")

    result = await db.execute(
        text("""
            INSERT INTO distance_pricing (min_km, max_km, surcharge, is_active, description, updated_by)
            VALUES (:min_km, :max_km, :surcharge, :active, :desc, :uid)
            RETURNING id, min_km, max_km, surcharge, is_active, description, updated_at
        """),
        {
            "min_km":    req.min_km,
            "max_km":    req.max_km,
            "surcharge": req.surcharge,
            "active":    req.is_active,
            "desc":      req.description,
            "uid":       current_user.id,
        },
    )
    row = result.fetchone()
    await db.commit()
    return dict(row._mapping)


@router.put("/distance/{pricing_id}", response_model=DistancePricingOut)
async def update_distance_pricing(
    pricing_id: int,
    req: DistancePricingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    # 현재 값 조회
    current = await db.execute(
        text("SELECT * FROM distance_pricing WHERE id = :id"), {"id": pricing_id}
    )
    row = current.fetchone()
    if not row:
        raise HTTPException(404, "거리 요금 설정을 찾을 수 없습니다")

    new_min = req.min_km      if req.min_km      is not None else float(row.min_km)
    new_max = req.max_km      if req.max_km      is not None else (float(row.max_km) if row.max_km else None)
    new_sur = req.surcharge   if req.surcharge   is not None else row.surcharge
    new_act = req.is_active   if req.is_active   is not None else row.is_active
    new_dsc = req.description if req.description is not None else row.description

    if new_max is not None and new_max <= new_min:
        raise HTTPException(400, "max_km은 min_km보다 커야 합니다")

    result = await db.execute(
        text("""
            UPDATE distance_pricing
            SET min_km = :min_km, max_km = :max_km, surcharge = :surcharge,
                is_active = :active, description = :desc,
                updated_at = NOW(), updated_by = :uid
            WHERE id = :id
            RETURNING id, min_km, max_km, surcharge, is_active, description, updated_at
        """),
        {
            "min_km":    new_min,
            "max_km":    new_max,
            "surcharge": new_sur,
            "active":    new_act,
            "desc":      new_dsc,
            "uid":       current_user.id,
            "id":        pricing_id,
        },
    )
    await db.commit()
    return dict(result.fetchone()._mapping)


@router.delete("/distance/{pricing_id}", status_code=204)
async def delete_distance_pricing(
    pricing_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("ADMIN")),
):
    result = await db.execute(
        text("DELETE FROM distance_pricing WHERE id = :id RETURNING id"),
        {"id": pricing_id},
    )
    if not result.fetchone():
        raise HTTPException(404, "거리 요금 설정을 찾을 수 없습니다")
    await db.commit()


# ── 요금 미리보기 ─────────────────────────────────────────────────

@router.post("/preview")
async def preview_price(
    req: PricePreviewRequest,
    db: AsyncSession  = Depends(get_db),
    _=Depends(require_role("ADMIN")),
):
    """
    관리자가 기준 금액 + 위치 + 거리 입력 시
    날씨·거리 적용 후 최종 예상 요금을 반환합니다.
    """
    from app.services.weather import get_weather_multiplier

    weather_condition, weather_mult = await get_weather_multiplier(req.lat, req.lon, db)

    dist_row = await db.execute(
        text("""
            SELECT surcharge FROM distance_pricing
            WHERE is_active = true
              AND min_km <= :km
              AND (max_km IS NULL OR max_km > :km)
            ORDER BY min_km DESC
            LIMIT 1
        """),
        {"km": req.distance_km},
    )
    dist_result = dist_row.fetchone()
    distance_surcharge = dist_result.surcharge if dist_result else 0

    weather_amount = int(round(req.base_amount * weather_mult))
    final_amount   = weather_amount + distance_surcharge

    return {
        "base_amount":        req.base_amount,
        "weather_condition":  weather_condition,
        "weather_multiplier": weather_mult,
        "weather_amount":     weather_amount,
        "distance_km":        req.distance_km,
        "distance_surcharge": distance_surcharge,
        "final_amount":       final_amount,
        "breakdown": {
            "base":     req.base_amount,
            "weather":  weather_amount - req.base_amount,
            "distance": distance_surcharge,
            "total":    final_amount,
        },
    }
