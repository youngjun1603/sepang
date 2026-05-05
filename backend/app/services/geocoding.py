"""카카오 로컬 API 기반 주소 → 위경도 변환"""
from __future__ import annotations
from typing import Optional

import httpx
from app.core.config import settings


class GeocodeResult:
    def __init__(self, lat: float, lng: float, address: str):
        self.lat     = lat
        self.lng     = lng
        self.address = address


async def geocode_address(address: str) -> Optional[GeocodeResult]:
    """
    카카오 로컬 API로 주소를 위경도로 변환.
    API 키 미설정 시 None 반환 (개발 환경 fallback).
    """
    if not settings.KAKAO_MAP_REST_API_KEY:
        return None

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            "https://dapi.kakao.com/v2/local/search/address.json",
            params={"query": address, "size": 1},
            headers={"Authorization": f"KakaoAK {settings.KAKAO_MAP_REST_API_KEY}"},
        )

    if resp.status_code != 200:
        return None

    data = resp.json()
    docs = data.get("documents", [])
    if not docs:
        # 주소 검색 실패 → 키워드 검색으로 재시도
        return await _keyword_search(address)

    doc = docs[0]
    return GeocodeResult(
        lat=float(doc["y"]),
        lng=float(doc["x"]),
        address=doc.get("address_name", address),
    )


async def _keyword_search(query: str) -> Optional[GeocodeResult]:
    """주소 검색 실패 시 장소명 검색으로 fallback"""
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(
            "https://dapi.kakao.com/v2/local/search/keyword.json",
            params={"query": query, "size": 1},
            headers={"Authorization": f"KakaoAK {settings.KAKAO_MAP_REST_API_KEY}"},
        )

    if resp.status_code != 200:
        return None

    docs = resp.json().get("documents", [])
    if not docs:
        return None

    doc = docs[0]
    return GeocodeResult(
        lat=float(doc["y"]),
        lng=float(doc["x"]),
        address=doc.get("address_name", query),
    )
