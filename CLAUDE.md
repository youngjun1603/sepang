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

## 서비스 URL (도메인 연결 완료 ✅)

| 앱 | 운영 URL | Vercel 기본 URL |
|----|----------|-----------------|
| 고객 앱 | **sepang.kr** | sepang-customer.vercel.app |
| 점주 앱 | **partner.sepang.kr** | sepang-partner.vercel.app |
| 관리자 앱 | **admin.sepang.kr** | sepang-admin.vercel.app |
| API | **api.sepang.kr** | sepang-api.vercel.app |

DNS: A 레코드 `@`, `partner`, `admin` → `76.76.21.21` / CNAME `api` → `5bfcb480b34eff12.vercel-dns-017.com`

## 주요 기술 결정

- **FastAPI → Vercel Python Serverless**: `backend/vercel.json` (`@vercel/python`)
- **DB 연결**: Session Pooler (`aws-1-ap-northeast-1.pooler.supabase.com:5432`) + `NullPool` — 아래 트러블슈팅 참고
- **WebSocket 제거**: Supabase Realtime (`postgres_changes`)으로 실시간 추적
- **S3 제거**: Supabase Storage (`asyncio.to_thread`)으로 사진 업로드
- **Redis/Celery 제거**: Vercel Serverless 환경에서 불필요
- **next-pwa 교체**: `next-pwa@5.x` → `@ducanh2912/next-pwa@10.x` (webpack 호환)
- **DB 마이그레이션**: Alembic + asyncpg. 초기 스키마는 Supabase Management API로 직접 적용
- **MONITOR_API_TOKEN**: GitHub Actions 모니터링용 정적 장기 토큰 (JWT 대신 사용)

## 폴더 구조

```
sepang/
├── backend/          FastAPI + Alembic (Vercel Python Serverless)
│   ├── app/
│   │   ├── api/v1/   orders, auth, admin, users, settlements, reviews, geocoding, payments
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
│   └── functions/    send-sms, sla-monitor, create-weekly-settlements, send-d3-reminder, send-friday-push
└── .github/workflows/
    ├── 01_ci.yml              CI (lint, type check, test)
    ├── 02_cd_vercel.yml       CD (Vercel 4개 프로젝트 + Edge Functions)
    ├── 04_monitoring.yml      헬스체크 + SLA 감시 (10분마다)
    └── 05_scheduled_jobs.yml  정기 배치 작업
```

## 환경변수

### 백엔드 (Vercel)
```
DATABASE_URL              postgresql+asyncpg://postgres.apghgbecayjfsuswaggf:Sepang2026!@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres
JWT_SECRET                (Vercel 환경변수에 설정됨)
ENVIRONMENT               production
SUPABASE_URL              https://apghgbecayjfsuswaggf.supabase.co
SUPABASE_ANON_KEY         (Vercel 환경변수에 설정됨)
SUPABASE_SERVICE_ROLE_KEY (Vercel 환경변수에 설정됨)
MONITOR_API_TOKEN         (Vercel + GitHub Secret 동일값 설정됨)
TOSS_CLIENT_KEY           (클라이언트 발급 후 등록 필요)
TOSS_SECRET_KEY           (클라이언트 발급 후 등록 필요)
NAVER_SENS_*              (클라이언트 발급 후 등록 필요)
FCM_SERVICE_ACCOUNT_JSON  (등록 완료)
VAPID_PRIVATE_KEY         (등록 완료)
VAPID_PUBLIC_KEY          (등록 완료)
KAKAO_MAP_REST_API_KEY    (등록 완료)
```

### 프론트엔드 (Vercel)
```
NEXT_PUBLIC_SUPABASE_URL      https://apghgbecayjfsuswaggf.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY (설정됨)
NEXT_PUBLIC_API_URL           https://api.sepang.kr
```

### GitHub Secrets
```
VERCEL_TOKEN                  PAT (설정됨)
VERCEL_ORG_ID                 team_JBhMZkd4FWWdIinWku39uvFQ
VERCEL_PROJECT_ID_BACKEND     prj_2pECSbwJ4BMy4iM7R9mp2XI1XSSc
VERCEL_PROJECT_ID_CUSTOMER    prj_q9hn6s3gExBIBH5xckqSgvKHVBWv
VERCEL_PROJECT_ID_PARTNER     prj_Ynt1tle9JFSmwm3A1T3dLJwOAY6v
VERCEL_PROJECT_ID_ADMIN       prj_q40A5Llde4FWxYnal6JHNVWO5Hj0
SUPABASE_DIRECT_URL           postgresql+asyncpg://postgres:Sepang2026!@db.apghgbecayjfsuswaggf.supabase.co:5432/postgres
SUPABASE_PROJECT_REF          apghgbecayjfsuswaggf
SUPABASE_ACCESS_TOKEN         (설정됨)
SUPABASE_URL                  https://apghgbecayjfsuswaggf.supabase.co
SUPABASE_ANON_KEY             (설정됨)
MONITOR_API_TOKEN             (설정됨)
SLACK_WEBHOOK_URL             배포 알림 (없어도 continue-on-error)
```

## 주요 API 엔드포인트

```
GET  /health                         헬스체크
GET  /api/v1/health/db               DB 연결 확인
GET  /api/v1/health/storage          Storage 연결 확인

POST /api/v1/auth/send-otp           OTP 발송
POST /api/v1/auth/verify-otp         OTP 인증 + JWT 발급
POST /api/v1/auth/partner/login      점주 로그인 (사업자번호)
POST /api/v1/auth/admin/login        관리자 1단계 로그인
POST /api/v1/auth/admin/otp          관리자 2FA OTP 검증
POST /api/v1/auth/refresh            JWT 갱신

POST /api/v1/orders/                 주문 생성 (CUSTOMER)
PATCH /api/v1/orders/{id}/status     상태 변경 (PARTNER)
POST /api/v1/orders/{id}/photos      사진 업로드 → Supabase Storage
GET  /api/v1/orders/partner/nearby   반경 내 대기 주문 (PostGIS)

GET  /api/v1/users/me                내 프로필
POST /api/v1/geocode/                주소 → 위경도 (카카오 Maps)
GET  /api/v1/admin/sla-at-risk       SLA 위험 주문 (MONITOR_API_TOKEN 또는 ADMIN JWT)
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

-- 등록된 기본 데이터
coupons: WELCOME3000 (신규가입 3,000원), REVIEW100 (리뷰작성 적립)
```

## DB 연결 핵심 주의사항

Vercel(IPv4 전용) + Supabase 연결 시 반드시 아래 규칙 준수:

| 항목 | 올바른 설정 | 잘못된 설정 |
|------|------------|------------|
| 스키마 | `postgresql+asyncpg://` | `postgresql://` → psycopg2 오류 |
| 호스트 | `aws-1-ap-northeast-1.pooler.supabase.com` | `aws-0-...` → ENOTFOUND |
| 포트 | `5432` (Session Pooler) | `6543` (Transaction Pooler) → DuplicatePreparedStatementError |
| Direct URL | 사용 불가 (IPv6 전용) | `db.*.supabase.co` → Vercel에서 연결 불가 |
| Pool 설정 | `NullPool` (serverless 최적화) | QueuePool → prepared statement 충돌 |

`SUPABASE_DIRECT_URL` (GitHub Secret, 마이그레이션 전용): `db.*.supabase.co:5432` 사용 (Direct Connection, asyncpg)

## 트러블슈팅 이력

### 에러 1: `ENOTFOUND` — tenant/user not found
- **원인**: DATABASE_URL 호스트가 `aws-0-ap-northeast-1`으로 설정됨. 실제 프로젝트 pooler는 `aws-1-`
- **수정**: `aws-0-` → `aws-1-`

### 에러 2: `ModuleNotFoundError: No module named 'psycopg2'`
- **원인**: DATABASE_URL 스키마가 `postgresql://`로 입력됨. SQLAlchemy가 기본 드라이버(psycopg2)를 찾으려 함
- **수정**: `postgresql://` → `postgresql+asyncpg://`

### 에러 3: `password authentication failed for user "postgres"`
- **원인**: Supabase DB 비밀번호 재설정 후 Vercel 환경변수에 이전 비밀번호가 그대로 남아 있었음
- **수정**: Supabase 비밀번호 재설정 → Vercel DATABASE_URL 전체 교체

### 에러 4: `DuplicatePreparedStatementError` — prepared statement already exists
- **원인**: Transaction Pooler(port 6543)는 트랜잭션마다 다른 백엔드 커넥션을 배정함. asyncpg가 이전 트랜잭션에서 생성한 prepared statement 이름을 새 백엔드에서 다시 생성하려다 충돌
- **수정 1**: `NullPool` 적용 — 요청마다 새 커넥션 생성, 재사용 없음 (`backend/app/core/database.py`)
- **수정 2**: Session Pooler(port 5432)로 전환 — 세션 동안 동일 백엔드 유지, prepared statement 충돌 없음

### 에러 5: SLA 모니터링 항상 실패
- **원인**: `.github/workflows/04_monitoring.yml`의 sla-monitor 잡 `if` 조건이 `*/5 * * * *`를 체크하지만 실제 cron은 `*/10 * * * *`로 설정되어 조건이 매칭되지 않음
- **수정**: `if` 조건을 `*/10 * * * *` 또는 `workflow_dispatch`로 수정

### 에러 6: Vercel 재배포 시 환경변수 미적용
- **원인**: Vercel 대시보드 "Redeploy" 버튼은 prebuilt 아티팩트를 재사용 → 환경변수 변경 미적용
- **수정**: 코드 변경(또는 empty commit)을 push하여 GitHub Actions CD 통해 fresh build 트리거

### 에러 7: `api.sepang.kr` SSL 핸드셰이크 실패 (HTTP 000)
- **원인**: `vercel alias set`으로 단순 alias만 생성 → Vercel이 SSL 인증서를 발급하지 않음. 다른 3개 도메인은 `vercel domains add`(프로젝트 도메인)로 등록되어 SSL이 정상 발급되었으나 `api.sepang.kr`만 누락
- **수정**: Vercel 대시보드 → sepang-api → Settings → Domains → `api.sepang.kr` 직접 추가 → DNS를 A레코드에서 CNAME(`5bfcb480b34eff12.vercel-dns-017.com`)으로 변경 → Valid Configuration 확인

## 남은 작업

1. ~~**도메인 연결**~~ ✅ 완료 (2026-05-13) — 4개 도메인 모두 연결 및 SSL 발급 완료

2. **Toss Payments**: 클라이언트가 API 키 발급 → `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY` Vercel sepang-api 등록

3. **NAVER SENS**: 클라이언트가 API 키 발급 → `NAVER_SENS_SERVICE_ID`, `NAVER_SENS_ACCESS_KEY`, `NAVER_SENS_SECRET_KEY`, `NAVER_SENS_SENDER` Vercel sepang-api 등록
