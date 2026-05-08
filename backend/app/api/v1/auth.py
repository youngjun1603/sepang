"""
인증 API — FastAPI
──────────────────
POST /api/v1/auth/send-otp       고객 OTP 발송
POST /api/v1/auth/verify-otp     고객 OTP 검증 + JWT
POST /api/v1/auth/partner/login  점주 로그인 (사업자번호)
POST /api/v1/auth/admin/login    관리자 1단계 로그인
POST /api/v1/auth/admin/otp      관리자 OTP 검증 (2FA)
POST /api/v1/auth/refresh        JWT 갱신
GET  /api/v1/users/me            내 정보
"""
import secrets, hashlib, hmac
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field
import jwt
import pyotp               # TOTP (관리자 2FA)
import bcrypt
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.config import settings
from app.core.auth import get_current_user
from app.services.notification import send_sms

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES  = 60 * 24       # 1일
REFRESH_TOKEN_EXPIRE_DAYS    = 30
OTP_EXPIRE_MINUTES           = 3
MAX_OTP_ATTEMPTS             = 5
MAX_ADMIN_LOGIN_FAILURES     = 5


# ── Schemas ────────────────────────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    phone: str = Field(..., pattern=r"^010\d{8}$")

class VerifyOTPRequest(BaseModel):
    phone:  str = Field(..., pattern=r"^010\d{8}$")
    code:   str = Field(..., min_length=4, max_length=6)
    name:   Optional[str] = Field(None, max_length=50)

class PartnerLoginRequest(BaseModel):
    business_number: str = Field(..., pattern=r"^\d{3}-\d{2}-\d{5}$")
    password:        str = Field(..., min_length=8)

class AdminLoginRequest(BaseModel):
    email:    str
    password: str = Field(..., min_length=12)

class AdminOTPRequest(BaseModel):
    temp_token: str   # 1단계 완료 임시 토큰
    otp_code:   str = Field(..., min_length=6, max_length=6)


# ── JWT Helpers ────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, role: str, shop_id: Optional[str] = None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict = {"sub": user_id, "role": role, "exp": exp, "type": "access"}
    if shop_id:
        payload["shop_id"] = shop_id
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": user_id, "exp": exp, "type": "refresh"},
        settings.JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

def create_temp_token(user_id: str, purpose: str) -> str:
    """관리자 2FA 중간 단계 토큰 (10분 유효)"""
    exp = datetime.now(timezone.utc) + timedelta(minutes=10)
    return jwt.encode(
        {"sub": user_id, "purpose": purpose, "exp": exp, "type": "temp"},
        settings.JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


# ── 고객 인증 (휴대폰 OTP) ────────────────────────────────────────────────────

@router.post("/send-otp")
@limiter.limit("5/minute")
async def send_otp(request: Request, req: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    """
    OTP 발송
    - 3분 유효, 최대 5회 시도
    - 기존 미사용 OTP 무효화
    """
    # 기존 OTP 무효화
    await db.execute(
        text("""
            UPDATE otp_verifications
            SET expires_at = NOW()
            WHERE phone = :phone AND verified_at IS NULL AND expires_at > NOW()
        """),
        {"phone": req.phone}
    )

    code = secrets.randbelow(10**6)
    code_str = str(code).zfill(6)
    exp = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)

    await db.execute(
        text("""
            INSERT INTO otp_verifications (phone, code, purpose, expires_at)
            VALUES (:phone, :code, 'LOGIN', :exp)
        """),
        {"phone": req.phone, "code": hashlib.sha256(code_str.encode()).hexdigest(), "exp": exp}
    )
    await db.commit()

    # SMS 발송 (실서비스: 카카오 알림톡 or 네이버 클라우드 SENS)
    await send_sms(req.phone, f"[세팡] 인증번호 {code_str} (3분 유효)")

    return {"message": "인증번호가 발송되었습니다", "expires_in": 180}


@router.post("/verify-otp")
async def verify_otp(req: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    """
    OTP 검증 + 가입/로그인 통합
    - 기존 회원: 로그인
    - 신규: 자동 회원가입 후 로그인
    """
    code_hash = hashlib.sha256(req.code.encode()).hexdigest()
    result = await db.execute(
        text("""
            SELECT id, attempts
            FROM otp_verifications
            WHERE phone = :phone AND purpose = 'LOGIN'
              AND expires_at > NOW() AND verified_at IS NULL
            ORDER BY created_at DESC LIMIT 1
        """),
        {"phone": req.phone}
    )
    otp_row = result.fetchone()
    if not otp_row:
        raise HTTPException(400, "인증번호가 만료되었거나 존재하지 않습니다")

    if otp_row.attempts >= MAX_OTP_ATTEMPTS:
        raise HTTPException(429, "시도 횟수 초과. 인증번호를 다시 요청해 주세요")

    # 코드 검증
    actual_result = await db.execute(
        text("SELECT code FROM otp_verifications WHERE id = :id"),
        {"id": otp_row.id}
    )
    stored_hash = actual_result.scalar()
    if not hmac.compare_digest(stored_hash, code_hash):
        await db.execute(
            text("UPDATE otp_verifications SET attempts = attempts + 1 WHERE id = :id"),
            {"id": otp_row.id}
        )
        await db.commit()
        raise HTTPException(400, f"인증번호가 올바르지 않습니다 ({MAX_OTP_ATTEMPTS - otp_row.attempts - 1}회 남음)")

    # OTP 사용 처리
    await db.execute(
        text("UPDATE otp_verifications SET verified_at = NOW() WHERE id = :id"),
        {"id": otp_row.id}
    )

    # 사용자 조회 or 생성
    user_result = await db.execute(
        text("SELECT id, role FROM users WHERE phone = :phone AND is_active"),
        {"phone": req.phone}
    )
    user = user_result.fetchone()

    if not user:
        # 신규 가입
        new_user = await db.execute(
            text("""
                INSERT INTO users (role, name, phone)
                VALUES ('CUSTOMER', :name, :phone)
                RETURNING id, role
            """),
            {"name": req.name or req.phone[:4] + "****", "phone": req.phone}
        )
        user = new_user.fetchone()
        # 신규 가입 쿠폰 발급 (WELCOME3000 쿠폰이 활성화된 경우에만)
        await db.execute(
            text("""
                INSERT INTO user_coupons (user_id, coupon_id)
                SELECT :uid, id FROM coupons
                WHERE code = 'WELCOME3000' AND is_active
                LIMIT 1
                ON CONFLICT DO NOTHING
            """),
            {"uid": str(user.id)}
        )

    await db.commit()

    return {
        "access_token":  create_access_token(str(user.id), user.role),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type":    "Bearer",
        "user_id":       str(user.id),
    }


# ── 점주 인증 ─────────────────────────────────────────────────────────────────

@router.post("/partner/login")
@limiter.limit("10/minute")
async def partner_login(request: Request, req: PartnerLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT u.id, u.role, u.password_hash, u.is_active, s.id AS shop_id
            FROM users u
            JOIN shops s ON s.owner_id = u.id
            WHERE u.business_number = :bn AND u.role = 'PARTNER'
            LIMIT 1
        """),
        {"bn": req.business_number}
    )
    user = result.fetchone()
    if not user or not user.is_active or not user.password_hash:
        raise HTTPException(401, "사업자번호 또는 비밀번호가 올바르지 않습니다")

    if not bcrypt.checkpw(req.password.encode(), user.password_hash.encode()):
        raise HTTPException(401, "사업자번호 또는 비밀번호가 올바르지 않습니다")

    await db.execute(
        text("UPDATE users SET last_login_at = NOW() WHERE id = :id"),
        {"id": user.id}
    )
    await db.commit()

    return {
        "access_token":  create_access_token(str(user.id), "PARTNER", str(user.shop_id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "shop_id":       str(user.shop_id),
    }


# ── 관리자 인증 (2단계) ───────────────────────────────────────────────────────

@router.post("/admin/login")
@limiter.limit("5/minute")
async def admin_login(
    req:     AdminLoginRequest,
    request: Request,
    db:      AsyncSession = Depends(get_db),
):
    """1단계: 이메일 + 비밀번호 검증 → 임시 토큰 발급"""
    client_ip = request.client.host
    if not _is_allowed_ip(client_ip):
        raise HTTPException(403, "접근이 허용되지 않은 IP입니다")

    result = await db.execute(
        text("SELECT id, password_hash, is_active FROM users WHERE email = :email AND role = 'ADMIN'"),
        {"email": req.email}
    )
    admin = result.fetchone()
    if not admin or not admin.is_active:
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")

    if not bcrypt.checkpw(req.password.encode(), admin.password_hash.encode()):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")

    # 감사 로그
    await db.execute(
        text("INSERT INTO admin_audit_logs (admin_id, ip_address, path, action) VALUES (:aid, :ip, '/auth/admin/login', '1FA_SUCCESS')"),
        {"aid": admin.id, "ip": client_ip}
    )
    await db.commit()

    return {"temp_token": create_temp_token(str(admin.id), "ADMIN_2FA")}


@router.post("/admin/otp")
async def admin_verify_otp(req: AdminOTPRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """2단계: Google Authenticator TOTP 검증 → 최종 JWT"""
    try:
        payload = jwt.decode(req.temp_token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("purpose") != "ADMIN_2FA":
            raise ValueError("Invalid token purpose")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        raise HTTPException(401, "임시 토큰이 유효하지 않습니다")

    admin_id = payload["sub"]
    result = await db.execute(
        text("SELECT totp_secret FROM users WHERE id = :id"),
        {"id": admin_id}
    )
    row = result.fetchone()
    if not row or not row.totp_secret:
        raise HTTPException(400, "OTP가 설정되지 않은 계정입니다")

    totp = pyotp.TOTP(row.totp_secret)
    if not totp.verify(req.otp_code, valid_window=1):  # ±30초 허용
        raise HTTPException(401, "OTP 코드가 올바르지 않습니다")

    # 감사 로그
    await db.execute(
        text("INSERT INTO admin_audit_logs (admin_id, ip_address, path, action) VALUES (:aid, :ip, '/auth/admin/otp', '2FA_SUCCESS')"),
        {"aid": admin_id, "ip": request.client.host}
    )
    await db.commit()

    return {
        "access_token":  create_access_token(admin_id, "ADMIN"),
        "refresh_token": create_refresh_token(admin_id),
    }


@router.post("/refresh")
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise ValueError()
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        raise HTTPException(401, "유효하지 않은 리프레시 토큰입니다")

    result = await db.execute(
        text("SELECT id, role FROM users WHERE id = :id AND is_active"),
        {"id": payload["sub"]}
    )
    user = result.fetchone()
    if not user:
        raise HTTPException(401, "사용자를 찾을 수 없습니다")

    return {"access_token": create_access_token(str(user.id), user.role)}


def _is_allowed_ip(ip: str) -> bool:
    """IP 허용 목록 검증. ADMIN_ALLOWED_IPS 환경변수가 비어있으면 모든 IP 허용."""
    allowlist = settings.ADMIN_ALLOWED_IPS.strip()
    if not allowlist:
        return True
    allowed = [a.strip() for a in allowlist.split(",") if a.strip()]
    return any(ip.startswith(a) for a in allowed)

