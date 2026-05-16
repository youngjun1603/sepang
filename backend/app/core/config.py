"""앱 설정 — Pydantic Settings"""
from pydantic_settings import BaseSettings
from typing import List
import json
import warnings

class Settings(BaseSettings):
    # Database (Supabase Transaction Pooler 또는 로컬 PostgreSQL)
    DATABASE_URL:   str = "postgresql+asyncpg://sepang:password@localhost:5432/sepang"

    # Auth
    JWT_SECRET:     str = "change-me-in-production"
    JWT_ALGORITHM:  str = "HS256"

    # Supabase
    SUPABASE_URL:               str = ""
    SUPABASE_ANON_KEY:          str = ""
    SUPABASE_SERVICE_ROLE_KEY:  str = ""   # 서버 전용

    # FCM (서비스 계정 JSON 문자열)
    FCM_SERVICE_ACCOUNT_JSON: str = ""

    # Web Push VAPID
    VAPID_PRIVATE_KEY:  str = ""
    VAPID_PUBLIC_KEY:   str = ""

    # 카카오
    KAKAO_APP_KEY:          str = ""
    KAKAO_SECRET_KEY:       str = ""
    KAKAO_SENDER_KEY:       str = ""
    KAKAO_MAP_REST_API_KEY: str = ""  # 로컬 API (주소 → 위경도)

    # 네이버 클라우드 SENS (SMS)
    NAVER_SENS_SERVICE_ID: str = ""
    NAVER_SENS_ACCESS_KEY: str = ""
    NAVER_SENS_SECRET_KEY: str = ""
    NAVER_SENS_SENDER:     str = ""   # 발신 번호 (010-XXXX-XXXX)

    # 토스페이먼츠
    TOSS_CLIENT_KEY: str = ""   # 클라이언트 키 (프론트엔드용)
    TOSS_SECRET_KEY: str = ""   # 시크릿 키 (서버용)

    # 관리자 IP 허용 목록 (콤마 구분, 비어있으면 모든 IP 허용)
    ADMIN_ALLOWED_IPS: str = ""

    # 모니터링 전용 정적 토큰 (GitHub Actions → sla-at-risk 엔드포인트용)
    MONITOR_API_TOKEN: str = ""

    # 기상청 API (날씨 요금 적용) — data.go.kr 신청
    KMA_SERVICE_KEY: str = ""

    # App
    ENVIRONMENT:    str = "production"
    DEBUG:          bool = False
    CORS_ORIGINS:   List[str] = [
        "https://sepang.kr",
        "https://partner.sepang.kr",
        "https://admin.sepang.kr",
        "https://sepang-customer.vercel.app",
        "https://sepang-partner.vercel.app",
        "https://sepang-admin.vercel.app",
    ]

    def model_post_init(self, __context):
        if self.ENVIRONMENT == "production" and self.JWT_SECRET == "change-me-in-production":
            warnings.warn(
                "SECURITY: JWT_SECRET is using the default value in production. "
                "Set JWT_SECRET environment variable in Vercel dashboard.",
                stacklevel=2
            )

    class Config:
        env_file = ".env"
        extra   = "ignore"

settings = Settings()
