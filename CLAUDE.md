# 세팡 (Sepang) — 세탁 플랫폼

B2C 고객 + B2B 파트너(점주) + 관리자 3개 플랫폼. FastAPI + Next.js PWA + Capacitor.

## 인프라

| 항목 | 값 |
|------|-----|
| 프론트엔드 | Vercel — customer / partner / admin |
| 백엔드 API | Vercel Python Serverless (FastAPI) |
| DB | Supabase PostgreSQL + PostGIS (프로젝트: `apghgbecayjfsuswaggf`, 리전: ap-northeast-1) |
| 스토리지 | Supabase Storage — 버킷 `order-photos` (최대 10MB) |
| 실시간 | Supabase Realtime — `orders` 테이블 postgres_changes 구독 |
| SMS | Supabase Edge Function `send-sms` — NAVER SENS |
| GitHub | https://github.com/youngjun1603/sepang |

## Vercel 프로젝트 ID

```
sepang-api      prj_2pECSbwJ4BMy4iM7R9mp2XI1XSSc
sepang-customer prj_q9hn6s3gExBIBH5xckqSgvKHVBWv
sepang-partner  prj_Ynt1tle9JFSmwm3A1T3dLJwOAY6v
sepang-admin    prj_q40A5Llde4FWxYnal6JHNVWO5Hj0
Org ID          team_JBhMZkd4FWWdIinWku39uvFQ
```

## 서비스 URL (배포 후)

| 앱 | 기본 URL | 커스텀 도메인 |
|----|----------|---------------|
| 고객 앱 | sepang-customer.vercel.app | sepang.kr |
| 점주 앱 | sepang-partner.vercel.app | partner.sepang.kr |
| 관리자 앱 | sepang-admin.vercel.app | admin.sepang.kr |
| API | sepang-api.vercel.app | api.sepang.kr |

## 주요 기술 결정

- **FastAPI → Vercel Python Serverless**: `backend/vercel.json` (`@vercel/python`)
- **WebSocket 제거**: Supabase Realtime (`postgres_changes`)으로 실시간 추적
- **S3 제거**: Supabase Storage (`asyncio.to_thread`)으로 사진 업로드
- **Redis/Celery 제거**: Vercel Serverless 환경에서 불필요
- **next-pwa 교체**: `next-pwa@5.x` → `@ducanh2912/next-pwa@10.x` (webpack 호환)
- **DB 마이그레이션**: Alembic + asyncpg (`postgresql+asyncpg://`). alembic_version 테이블에 0003 스탬프됨 (초기 스키마는 Management API로 직접 적용)

## 폴더 구조

```
sepang/
├── backend/          FastAPI + Alembic (Vercel Python Serverless)
│   ├── app/
│   │   ├── api/v1/   orders, auth, admin, users, settlements, reviews, geocoding
│   │   ├── core/     config, database, auth
│   │   ├── models/   order, shop, base
│   │   └── services/ notification (FCM/WebPush/SMS), geo, geocoding
│   └── vercel.json
├── frontend/
│   ├── shared/       api-client.ts, useAuth.ts, useOrder.ts
│   ├── customer/     Next.js 14 PWA (고객)
│   ├── partner/      Next.js 14 PWA (점주)
│   └── admin/        Next.js 14 (관리자)
├── supabase/
│   ├── config.toml
│   └── functions/send-sms/index.ts
└── .github/workflows/
    ├── 01_ci.yml         E2E + 보안 스캔
    └── 02_cd_vercel.yml  Vercel 4개 프로젝트 + Edge Functions 배포
```

## 환경변수

### 백엔드 (Vercel)
```
SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
DATABASE_URL    postgresql+asyncpg://postgres.apghgbecayjfsuswaggf:...@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres
JWT_SECRET      (Vercel 환경변수에 설정됨)
ENVIRONMENT     production
```

### 프론트엔드 (Vercel)
```
NEXT_PUBLIC_SUPABASE_URL     https://apghgbecayjfsuswaggf.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY  sb_publishable_...
NEXT_PUBLIC_API_URL           https://sepang-api.vercel.app
```

### GitHub Secrets
`VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID_BACKEND/CUSTOMER/PARTNER/ADMIN`
`SUPABASE_DB_URL, SUPABASE_PROJECT_REF, SUPABASE_ACCESS_TOKEN`

## 주요 API 엔드포인트

```
POST /api/v1/auth/send-otp           OTP 발송
POST /api/v1/auth/verify-otp         OTP 인증 + JWT 발급
POST /api/v1/auth/partner/login      점주 로그인 (사업자번호)
POST /api/v1/auth/admin/login        관리자 1단계 로그인
POST /api/v1/auth/admin/otp          관리자 2FA OTP 검증
POST /api/v1/auth/refresh            JWT 갱신 (?refresh_token=...)
POST /api/v1/orders/                 주문 생성 (CUSTOMER)
PATCH /api/v1/orders/{id}/status     상태 변경 (PARTNER)
POST /api/v1/orders/{id}/photos      사진 업로드 → Supabase Storage
GET  /api/v1/orders/partner/nearby   반경 내 대기 주문 (PostGIS)
GET  /api/v1/users/me                내 프로필
POST /api/v1/geocode/                주소 → 위경도 (카카오 Maps)
GET  /health                         헬스체크
```

## DB 스키마 핵심

```sql
-- 주요 테이블
users, shops, orders, order_status_history, order_photos
settlements, coupons, user_coupons, point_transactions
reviews, notifications, push_subscriptions
otp_verifications, admin_audit_logs

-- 주요 함수
accept_order(order_id, shop_id, version)  낙관적 잠금으로 주문 수락
get_nearby_orders(shop_id, radius_km)     PostGIS 반경 내 주문 조회
set_order_deadline()                       트리거: 주문 마감 12시간 자동 설정

-- RLS (Row Level Security)
orders: 고객은 본인 주문만, 점주는 담당 주문만 SELECT
users: 본인 프로필만 SELECT/UPDATE
service_role: 모든 테이블 전체 접근 (백엔드 API 사용)
```

## 수정 완료 (코드베이스 검증 후 픽스)

- `backend/app/api/v1/auth.py` — `validator` 미사용 import 제거 (Pydantic v2 deprecated)
- `backend/app/api/v1/auth.py` — `create_access_token`에 optional `shop_id` 추가; `partner_login`에서 JWT에 포함
- `backend/app/core/auth.py` — `get_current_user`에서 JWT payload의 `shop_id` 추출 → PARTNER 엔드포인트 `current_user.shop_id` 버그 수정
- `.github/workflows/01_ci.yml` — `ruff`, `mypy`, `pytest unit/integration`, `alembic` 모두 `working-directory: backend` 추가
- `.github/workflows/01_ci.yml` — `redis` 서비스 제거, `REDIS_URL`/`S3_BUCKET`/`AWS_DEFAULT_REGION` 환경변수 제거
- `.github/workflows/01_ci.yml` — `frontend-typecheck` 잡: matrix 전략으로 customer/partner/admin 각각 독립 실행
- `next.config.js` (customer/partner) — `next-pwa@5.x` → `@ducanh2912/next-pwa@10.x`
- `package.json` (customer/partner/admin) — eslint `^9.x` → `^8.57.0` (eslint-config-next@14 호환)
- Supabase `config.toml` — 잘못된 auth 키 제거 (`refresh_token_rotation_enabled` 등)
- DB 스키마 — Supabase Management API로 직접 적용 (PostGIS, RLS, Realtime 포함)

## 남은 작업

1. **VERCEL_TOKEN 갱신 필수**: GitHub Secret `VERCEL_TOKEN`의 `vca_` 세션 토큰이 만료됨.
   vercel.com/account/tokens 에서 Personal Access Token(PAT) 생성 후 GitHub Secret 교체 필요.
   → 이 작업 전까지 CD 파이프라인 (02_cd_vercel.yml) 실행 불가

2. **도메인 연결**: sepang.kr, partner.sepang.kr, admin.sepang.kr, api.sepang.kr → Vercel DNS

3. **카카오 Maps 키**: https://developers.kakao.com — REST API 키 발급 후 Vercel 환경변수에 추가

4. **VAPID 키 생성**: `python -c "from py_vapid import Vapid; v=Vapid(); v.generate_keys()"`

5. **Firebase FCM**: 파트너 앱 푸시 알림용 서버 키 → `FCM_SERVER_KEY` 환경변수

6. **NAVER SENS**: SMS 발송 환경변수 설정 (Edge Function에서 사용)
