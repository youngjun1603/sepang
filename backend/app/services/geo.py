"""PostGIS 기반 반경 내 파트너 샵 조회"""
from __future__ import annotations
from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def find_nearby_shops(
    db: AsyncSession,
    lat: float,
    lng: float,
    radius_m: int = 5000,
) -> List[dict]:
    """
    ST_DWithin으로 반경 radius_m 미터 이내 활성 샵 목록 반환.
    shops 테이블에 location GEOGRAPHY(Point,4326) 컬럼이 있어야 함.
    """
    result = await db.execute(
        text("""
            SELECT
                id,
                name,
                ST_Distance(
                    location::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                ) AS distance_m
            FROM shops
            WHERE
                is_active = true
                AND ST_DWithin(
                    location::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius_m
                )
            ORDER BY distance_m
            LIMIT 20
        """),
        {"lat": lat, "lng": lng, "radius_m": radius_m},
    )
    rows = result.mappings().all()
    return [{"id": str(r["id"]), "name": r["name"], "distance_m": float(r["distance_m"])} for r in rows]
