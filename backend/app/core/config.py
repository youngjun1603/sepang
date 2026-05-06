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

    # FCM
    FCM_SERVER_KEY: str = ""

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

    # App
    ENVIRONMENT:    str = "production"
    DEBUG:          bool = False
    CORS_ORIGINS:   List[str] = ["https://sepang.kr", "https://partner.sepang.kr"]

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
