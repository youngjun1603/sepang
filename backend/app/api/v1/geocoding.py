"""
주소 → 위경도 변환 API
───────────────────────
POST /api/v1/geocode   주소를 위경도로 변환 (카카오 로컬 API 프록시)
GET  /api/v1/geocode/vapid-public-key  Web Push VAPID 공개키
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.geocoding import geocode_address
from app.core.config import settings

router = APIRouter(prefix="/geocode", tags=["geocode"])


class GeocodeRequest(BaseModel):
    address: str


class GeocodeResponse(BaseModel):
    lat:     float
    lng:     float
    address: str


@router.post("/", response_model=GeocodeResponse)
async def geocode(req: GeocodeRequest):
    """
    주소 문자열을 위경도로 변환.
    - 카카오 API 키 미설정 시 서울 중심 기본값 반환 (개발 환경용)
    """
    if not req.address.strip():
        raise HTTPException(400, "주소를 입력해 주세요")

    result = await geocode_address(req.address.strip())

    if result is None:
        # 카카오 API 미설정 또는 실패 → 개발용 기본값
        if not settings.KAKAO_MAP_REST_API_KEY:
            return GeocodeResponse(lat=37.5665, lng=126.9780, address=req.address)
        raise HTTPException(422, "주소를 찾을 수 없습니다. 더 구체적인 주소를 입력해 주세요.")

    return GeocodeResponse(lat=result.lat, lng=result.lng, address=result.address)


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """프론트엔드 Web Push 구독에 필요한 VAPID 공개키 반환"""
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(503, "Web Push가 설정되지 않았습니다")
    return {"public_key": settings.VAPID_PUBLIC_KEY}
