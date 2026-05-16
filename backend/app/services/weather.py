"""
기상청 ASOS 지상관측 시간자료 API 연동
End Point: https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList
- 위경도 → 가장 가까운 ASOS 관측소 매핑
- 강수량(rn_60m) / 신적설(dsnw) 기반 날씨 조건 판별
- 30분 인메모리 캐시 (Vercel cold start 대응)
"""
from __future__ import annotations
import math
from datetime import datetime, timezone, timedelta
from typing import Literal

import httpx

from app.core.config import settings

WeatherCondition = Literal["NONE", "RAIN", "SNOW", "RAIN_SNOW"]

# ── 주요 ASOS 관측소 (지점번호, 위도, 경도, 지점명) ─────────────────────────
# 출처: 기상청 기후자료 개방 포털 관측소 목록 기준
_ASOS_STATIONS: list[tuple[int, float, float, str]] = [
    (108, 37.5714, 126.9658, "서울"),
    (112, 37.4772, 126.6244, "인천"),
    (119, 37.2721, 127.0047, "수원"),
    (129, 37.8963, 127.7174, "춘천"),
    (131, 37.7501, 128.8956, "강릉"),
    (133, 36.3691, 127.3742, "대전"),
    (136, 36.5268, 126.3311, "보령"),
    (138, 36.0160, 129.3578, "포항"),
    (143, 35.8839, 128.6183, "대구"),
    (146, 35.8242, 127.1479, "전주"),
    (152, 35.5325, 129.3231, "울산"),
    (155, 35.1795, 128.5683, "창원"),
    (156, 35.1719, 126.8929, "광주"),
    (159, 35.1042, 129.0323, "부산"),
    (162, 34.8458, 128.4383, "통영"),
    (165, 34.8147, 126.3817, "목포"),
    (184, 33.5147, 126.5298, "제주"),
    (185, 33.2449, 126.5656, "서귀포"),
]

# ── 30분 캐시 {stn_id: (condition, expires_at)} ────────────────────────────
_cache: dict[int, tuple[WeatherCondition, datetime]] = {}
_CACHE_TTL_MIN = 30


def _nearest_station(lat: float, lng: float) -> int:
    """위경도에서 유클리드 거리 기준 가장 가까운 ASOS 지점번호 반환"""
    best_stn_id = _ASOS_STATIONS[0][0]
    best_dist = float("inf")
    for stn_id, slat, slng, _ in _ASOS_STATIONS:
        dist = math.sqrt((lat - slat) ** 2 + (lng - slng) ** 2)
        if dist < best_dist:
            best_dist = dist
            best_stn_id = stn_id
    return best_stn_id


def _kst_now() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


async def _fetch_asos(stn_id: int, kst: datetime) -> WeatherCondition:
    """
    ASOS API 호출 — 현재 시각 기준 1시간 강수량·신적설로 날씨 조건 판별.
    데이터가 없으면 직전 시각으로 재시도.
    """
    for hour_offset in (0, 1):  # 현재 시각 → 데이터 미수신 시 1시간 전 재시도
        target = kst - timedelta(hours=hour_offset)
        date_str = target.strftime("%Y%m%d")
        hour_str = f"{target.hour:02d}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList",
                    params={
                        "serviceKey": settings.KMA_SERVICE_KEY,
                        "pageNo":     1,
                        "numOfRows":  1,
                        "dataType":   "JSON",
                        "dataCd":     "ASOS",
                        "dateCd":     "HR",
                        "startDt":    date_str,
                        "startHh":    hour_str,
                        "endDt":      date_str,
                        "endHh":      hour_str,
                        "stnIds":     str(stn_id),
                    },
                )
            body = resp.json().get("response", {}).get("body", {})
            items = body.get("items", {})
            if not items:
                continue
            item_list = items.get("item", [])
            if not item_list:
                continue

            item = item_list[0] if isinstance(item_list, list) else item_list

            # 1시간 강수량 (mm) — rn_60m 우선, 없으면 rn
            rn_raw  = item.get("rn_60m") or item.get("rn") or "0"
            # 신적설 (cm)
            dsnw_raw = item.get("dsnw") or "0"

            rn   = float(rn_raw)   if str(rn_raw).replace(".", "", 1).lstrip("-").isdigit() else 0.0
            dsnw = float(dsnw_raw) if str(dsnw_raw).replace(".", "", 1).lstrip("-").isdigit() else 0.0

            if rn > 0 and dsnw > 0:
                return "RAIN_SNOW"
            if dsnw > 0:
                return "SNOW"
            if rn > 0:
                return "RAIN"
            return "NONE"

        except Exception:
            continue

    return "NONE"


async def get_weather_condition(lat: float, lng: float) -> WeatherCondition:
    """
    현재 위치의 강수 조건 반환.
    KMA_SERVICE_KEY 미설정 시 NONE 반환 (graceful fallback).
    """
    if not settings.KMA_SERVICE_KEY:
        return "NONE"

    stn_id = _nearest_station(lat, lng)
    now_utc = datetime.now(timezone.utc)

    cached = _cache.get(stn_id)
    if cached and cached[1] > now_utc:
        return cached[0]

    condition = await _fetch_asos(stn_id, _kst_now())
    _cache[stn_id] = (condition, now_utc + timedelta(minutes=_CACHE_TTL_MIN))
    return condition


async def get_weather_multiplier(
    lat: float, lng: float, db
) -> tuple[WeatherCondition, float]:
    """
    날씨 조건과 요금 배수 반환.
    weather_pricing 테이블의 활성 설정 기준.
    """
    from sqlalchemy import text

    condition = await get_weather_condition(lat, lng)
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
