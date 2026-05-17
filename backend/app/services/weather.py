"""
기상청 초단기실황 API 연동
──────────────────────────
End Point: https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst
- 위경도 → 기상청 5km 격자 좌표 변환 (Lambert Conformal Conic)
- PTY(강수형태) 코드로 비/눈 실시간 판별 (10분 갱신)
- 30분 인메모리 캐시 (Vercel cold start 대응)

신청: data.go.kr → 기상청_단기예보 ((구)_동네예보) 조회서비스 → 활용신청
"""
from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from typing import Literal

import httpx

from app.core.config import settings

WeatherCondition = Literal["NONE", "RAIN", "SNOW", "RAIN_SNOW"]

# ── Lambert Conformal Conic 변환 상수 (기상청 공식값) ─────────────────────────
_RE     = 6371.00877
_GRID   = 5.0
_SLAT1  = 30.0
_SLAT2  = 60.0
_OLON   = 126.0
_OLAT   = 38.0
_XO     = 43
_YO     = 136
_DEGRAD = math.pi / 180.0


def _latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위경도 → 기상청 격자(nx, ny) 변환"""
    slat1 = _SLAT1 * _DEGRAD
    slat2 = _SLAT2 * _DEGRAD
    olon  = _OLON  * _DEGRAD
    olat  = _OLAT  * _DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf ** sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = _RE / _GRID * sf / (ro ** sn)

    ra = math.tan(math.pi * 0.25 + lat * _DEGRAD * 0.5)
    ra = _RE / _GRID * sf / (ra ** sn)

    theta = lon * _DEGRAD - olon
    if theta >  math.pi: theta -= 2.0 * math.pi
    if theta < -math.pi: theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + _XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + _YO + 0.5)
    return nx, ny


# ── PTY 강수형태 코드 매핑 ─────────────────────────────────────────────────────
# 0=없음, 1=비, 2=비/눈, 3=눈, 5=빗방울, 6=빗방울눈날림, 7=눈날림
_PTY_MAP: dict[str, WeatherCondition] = {
    "0": "NONE",
    "1": "RAIN",
    "2": "RAIN_SNOW",
    "3": "SNOW",
    "5": "RAIN",
    "6": "RAIN_SNOW",
    "7": "SNOW",
}

# ── 인메모리 캐시 {(nx, ny): (condition, expires_at)} ─────────────────────────
_cache: dict[tuple[int, int], tuple[WeatherCondition, datetime]] = {}
_CACHE_TTL_MIN = 30


def _base_time() -> tuple[str, str]:
    """초단기실황 base_date / base_time 계산 (직전 정각 기준)"""
    kst = datetime.now(timezone(timedelta(hours=9)))
    base = kst.replace(minute=0, second=0, microsecond=0)
    return base.strftime("%Y%m%d"), base.strftime("%H%M")


async def get_weather_condition(lat: float, lon: float) -> WeatherCondition:
    """
    현재 위치의 강수 형태 반환 (PTY 기준).
    KMA_SERVICE_KEY 미설정 시 NONE 반환 (graceful fallback).
    """
    if not settings.KMA_SERVICE_KEY:
        return "NONE"

    nx, ny = _latlon_to_grid(lat, lon)
    now_utc = datetime.now(timezone.utc)

    cached = _cache.get((nx, ny))
    if cached and cached[1] > now_utc:
        return cached[0]

    base_date, base_time = _base_time()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst",
                params={
                    "serviceKey": settings.KMA_SERVICE_KEY,
                    "numOfRows":  10,
                    "pageNo":     1,
                    "dataType":   "JSON",
                    "base_date":  base_date,
                    "base_time":  base_time,
                    "nx":         nx,
                    "ny":         ny,
                },
            )
        data = resp.json()
        items = data["response"]["body"]["items"]["item"]
        pty = next((i["obsrValue"] for i in items if i["category"] == "PTY"), "0")
        condition: WeatherCondition = _PTY_MAP.get(str(int(float(pty))), "NONE")
    except Exception:
        condition = "NONE"

    _cache[(nx, ny)] = (condition, now_utc + timedelta(minutes=_CACHE_TTL_MIN))
    return condition


async def get_weather_multiplier(
    lat: float, lon: float, db
) -> tuple[WeatherCondition, float]:
    """
    날씨 조건과 요금 배수 반환.
    weather_pricing 테이블의 활성 설정 기준.
    """
    from sqlalchemy import text

    condition = await get_weather_condition(lat, lon)
    if condition == "NONE":
        return "NONE", 1.0

    row = await db.execute(
        text("""
            SELECT multiplier FROM weather_pricing
            WHERE condition = :cond AND is_active = true
            LIMIT 1
        """),
        {"cond": condition},
    )
    result = row.fetchone()
    multiplier = float(result.multiplier) if result else 1.0
    return condition, multiplier
