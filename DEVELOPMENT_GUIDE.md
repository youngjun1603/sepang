# 세팡 개발 가이드

## 프로젝트 구조

```
sepang/
├── backend/                        FastAPI 백엔드 (Vercel Python Serverless)
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── auth.py             OTP 인증 / 점주 로그인 / 관리자 2FA
│   │   │   ├── orders.py           주문 생성·조회·상태변경·취소·사진업로드
│   │   │   ├── admin.py            대시보드 KPI / 점포 관리 / SLA 감시
│   │   │   ├── users.py            프로필 / 포인트 / 쿠폰 / 영업 상태
│   │   │   ├── reviews.py          리뷰 작성·목록
│   │   │   ├── payments.py         Toss Payments 결제 준비·확인·취소
│   │   │   ├── settlements.py      정산 내역 조회
│   │   │   └── geocoding.py        주소 → 위경도 (카카오 Maps)
│   │   ├── core/
│   │   │   ├── config.py           환경변수 (pydantic-settings)
│   │   │   ├── database.py         AsyncSession + NullPool (Session Pooler)
│   │   │   └── auth.py             JWT 발급·검증 / 역할 미들웨어
│   │   ├── models/                 SQLAlchemy 모델
│   │   └── services/
│   │       ├── notification.py     FCM / Web Push / NAVER SENS SMS
│   │       ├── geo.py              PostGIS 반경 쿼리
│   │       └── geocoding.py        카카오 Maps REST API
│   ├── alembic/
│   │   └── versions/               DB 마이그레이션 (0001 ~ 0007)
│   ├── requirements.txt
│   └── vercel.json                 Vercel Python Serverless 진입점
│
├── frontend/
│   ├── shared/lib/api-client.ts    3개 앱 공통 API 클라이언트 + 타입
│   ├── customer/                   고객 앱 (Next.js 14 PWA)
│   │   ├── src/App.jsx             SPA 라우터 (RouterCtx)
│   │   └── pages/
│   │       ├── index.jsx           진입점
│   │       ├── payment/success.jsx Toss 결제 성공 리다이렉트
│   │       └── payment/fail.jsx    Toss 결제 실패 리다이렉트
│   ├── partner/                    점주 앱 (Next.js 14 PWA)
│   └── admin/                      관리자 콘솔 (Next.js 14)
│
└── supabase/
    └── functions/
        ├── send-sms/               SMS 발송 (NAVER SENS)
        ├── sla-monitor/            SLA 위반 감지 + FCM 알림
        ├── create-weekly-settlements/  주간 정산 자동 생성
        ├── send-d3-reminder/       D+3 리마인드 FCM 푸시
        └── send-friday-push/       금요일 Night 프로모션 푸시
```

## 로컬 개발 환경

### 백엔드

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env  # DATABASE_URL, JWT_SECRET 등 입력

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000
```

### 프론트엔드

```bash
# 고객 앱
cd frontend/customer
npm install --legacy-peer-deps
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# 점주 앱
cd frontend/partner
npm install --legacy-peer-deps
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# 관리자 앱
cd frontend/admin
npm install --legacy-peer-deps
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## DB 마이그레이션

```bash
cd backend

# 마이그레이션 실행 (GitHub Actions CD에서 자동 수행)
alembic upgrade head

# 현재 버전 확인
alembic current

# 롤백
alembic downgrade -1
```

> **주의:** Supabase Direct URL(`db.*.supabase.co`)은 IPv6 전용입니다.
> 로컬에서 마이그레이션을 실행하려면 IPv6 지원 환경이 필요합니다.
> 프로덕션 마이그레이션은 GitHub Actions CD(`02_cd_vercel.yml`)에서 자동 수행됩니다.

## DB 연결 규칙 (중요)

| 항목 | 올바른 설정 | 잘못된 설정 |
|------|-----------|------------|
| 스키마 | `postgresql+asyncpg://` | `postgresql://` |
| 호스트 | `aws-1-ap-northeast-1.pooler.supabase.com` | `aws-0-...` |
| 포트 | `5432` (Session Pooler) | `6543` (Transaction Pooler) |
| Pool 설정 | `NullPool` | QueuePool |

## 배포

### 자동 배포 (권장)

```
feature/* → develop  →  CI 통과  →  Vercel Preview 배포
develop   → main     →  DB 마이그레이션 → Vercel Production 배포 → 스모크 테스트
```

main 브랜치에 push하면 GitHub Actions(`02_cd_vercel.yml`)가 자동으로:
1. Alembic DB 마이그레이션 실행
2. 백엔드 (FastAPI) Vercel 배포
3. 고객·점주·관리자 앱 빌드 및 Vercel 배포
4. Supabase Edge Functions 배포
5. 스모크 테스트 (`/health` 엔드포인트 확인)

### Vercel 프로젝트 구성

| 프로젝트 | ID | 커스텀 도메인 |
|---------|-----|--------------|
| sepang-api | `prj_2pECSbwJ4BMy4iM7R9mp2XI1XSSc` | api.sepang.kr |
| sepang-customer | `prj_q9hn6s3gExBIBH5xckqSgvKHVBWv` | sepang.kr |
| sepang-partner | `prj_Ynt1tle9JFSmwm3A1T3dLJwOAY6v` | partner.sepang.kr |
| sepang-admin | `prj_q40A5Llde4FWxYnal6JHNVWO5Hj0` | admin.sepang.kr |

## 주요 API 엔드포인트

```
GET  /health                             헬스체크
GET  /api/v1/health/db                   DB 연결 확인
GET  /api/v1/health/storage              Storage 연결 확인

POST /api/v1/auth/send-otp               OTP 발송 (고객)
POST /api/v1/auth/verify-otp             OTP 인증 + JWT 발급
POST /api/v1/auth/partner/login          점주 로그인 (사업자번호)
POST /api/v1/auth/admin/login            관리자 1단계 로그인
POST /api/v1/auth/admin/otp              관리자 2FA OTP 검증
POST /api/v1/auth/refresh                JWT 갱신

POST /api/v1/orders/                     주문 생성
PATCH /api/v1/orders/{id}/status         상태 변경 (점주)
POST /api/v1/orders/{id}/cancel          주문 취소 (고객/관리자)
POST /api/v1/orders/{id}/photos          사진 업로드 → Supabase Storage
GET  /api/v1/orders/partner/nearby       반경 내 대기 주문 (PostGIS)

GET  /api/v1/users/me                    내 프로필
GET  /api/v1/users/me/points             포인트 잔액 + 내역
GET  /api/v1/users/me/coupons            보유 쿠폰 목록
PATCH /api/v1/users/me/availability      점주 영업 상태 토글

POST /api/v1/payments/prepare            결제 준비 (Toss)
POST /api/v1/payments/confirm            결제 승인
POST /api/v1/payments/{id}/cancel        결제 취소·환불

POST /api/v1/reviews/                    리뷰 작성 (+100P 자동 적립)
GET  /api/v1/reviews/shop/{id}           샵 리뷰 목록

GET  /api/v1/admin/dashboard             KPI 대시보드
GET  /api/v1/admin/orders                주문 관제
GET  /api/v1/admin/shops                 점포 현황
POST /api/v1/admin/shops                 점포 등록
GET  /api/v1/admin/sla-at-risk           SLA 위험 주문
POST /api/v1/admin/orders/{id}/force-cancel  강제 취소
```

## 핵심 비즈니스 로직

- **SLA**: 주문 생성 즉시 `deadline_at = ordered_at + 12h` DB 트리거 자동 설정
- **Geo-fencing**: PostGIS `ST_DWithin`으로 반경 3km 내 점포 자동 매칭
- **낙관적 잠금**: `accept_order()` DB 함수로 동시 수락 경쟁 방지
- **결제**: Toss Payments — 준비(prepare) → 승인(confirm) → 취소/환불(cancel)
- **쿠폰·포인트**: 주문 시 자동 차감, 취소 시 자동 복원
- **알림**: FCM(앱 푸시) + Web Push(PWA) + NAVER SENS SMS 병렬 발송
- **정산**: 건당 수수료 제외, 주 단위 자동 집계 (매주 월요일 01:00 KST)

## 모니터링

- **헬스체크**: GitHub Actions `04_monitoring.yml` — 10분마다 4개 엔드포인트 확인
- **SLA 감시**: 5분마다 SLA 위험 주문 체크 → 위반 시 Slack 알림
- **DB 일일 확인**: 매일 03:00 KST Supabase 연결 확인
