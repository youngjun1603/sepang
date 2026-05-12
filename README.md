# 세팡 (SEPANG) — 운영 시스템

> 12시간 이내 수거·세탁·배송 완료 플랫폼

## 서비스 URL

| 앱 | 주소 |
|----|------|
| 고객 앱 | https://sepang.kr |
| 점주 앱 | https://partner.sepang.kr |
| 관리자 콘솔 | https://admin.sepang.kr |
| API | https://api.sepang.kr |

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| 고객 앱 | Next.js 14 PWA (sepang.kr) |
| 점주 앱 | Next.js 14 PWA (partner.sepang.kr) |
| 관리자 콘솔 | Next.js 14 (admin.sepang.kr) |
| API | FastAPI → Vercel Python Serverless |
| Database | Supabase PostgreSQL + PostGIS |
| 실시간 | Supabase Realtime (postgres_changes) |
| 스토리지 | Supabase Storage (order-photos 버킷) |
| 푸시 알림 | FCM (Firebase Cloud Messaging) + Web Push |
| SMS | NAVER SENS (Supabase Edge Function) |
| 배치 작업 | Supabase Edge Functions + GitHub Actions 스케줄러 |
| CI/CD | GitHub Actions |
| 호스팅 | Vercel (4개 프로젝트) |

## 프로젝트 구조

```
sepang/
├── .github/workflows/
│   ├── 01_ci.yml               테스트 + 린트
│   ├── 02_cd_vercel.yml        CD — DB 마이그레이션 + Vercel 배포 (main/develop)
│   ├── 04_monitoring.yml       헬스 체크 + SLA 감시 (10분 간격)
│   └── 05_scheduled_jobs.yml   정기 배치 (D+3 리마인드, 금요일 푸시, 주간 정산)
│
├── backend/                    FastAPI 백엔드
│   ├── app/
│   │   ├── api/v1/             REST API 엔드포인트
│   │   │   ├── auth.py         OTP / 점주 로그인 / 관리자 2FA
│   │   │   ├── orders.py       주문 CRUD + 취소 + 사진 업로드
│   │   │   ├── admin.py        관리자 대시보드 + 점포 관리 + SLA
│   │   │   ├── users.py        프로필 + 포인트 + 쿠폰 + 영업 상태
│   │   │   ├── reviews.py      리뷰 작성 + 목록
│   │   │   ├── payments.py     Toss Payments 결제 준비/확인/취소
│   │   │   ├── settlements.py  정산 내역 조회
│   │   │   └── geocoding.py    주소 → 위경도 (카카오 Maps)
│   │   ├── core/               설정 + DB + 인증
│   │   ├── models/             SQLAlchemy 모델
│   │   └── services/           FCM / Web Push / SMS / 지오코딩
│   ├── alembic/versions/       DB 마이그레이션 (0001~0007)
│   └── vercel.json             Vercel Python Serverless 설정
│
├── frontend/
│   ├── shared/                 3개 앱 공유 코드
│   │   └── lib/api-client.ts   API 클라이언트 + 타입 정의
│   ├── customer/               고객 앱 (Next.js PWA)
│   ├── partner/                점주 앱 (Next.js PWA)
│   └── admin/                  관리자 콘솔 (Next.js)
│
└── supabase/
    └── functions/              Edge Functions
        ├── send-sms/           SMS 발송 (NAVER SENS)
        ├── sla-monitor/        SLA 위반 감지 + FCM 알림
        ├── create-weekly-settlements/  주간 정산 자동 생성
        ├── send-d3-reminder/   D+3 리마인드 푸시
        └── send-friday-push/   금요일 Night 프로모션 푸시
```

## 배포 플로우

```
feature/* → develop → CI 통과 → Vercel Preview 자동 배포
develop   → main   → DB 마이그레이션 → Vercel Production 배포 → 스모크 테스트
```

## 핵심 비즈니스 로직

- **SLA**: 주문 생성 즉시 `deadline_at = ordered_at + 12h` DB 트리거로 자동 설정
- **Geo-fencing**: PostGIS `ST_DWithin`으로 반경 3km 내 점포 자동 매칭
- **낙관적 잠금**: `accept_order()` DB 함수로 동시 수락 경쟁 방지
- **결제**: Toss Payments — 준비(prepare) → 승인(confirm) → 취소/환불(cancel)
- **쿠폰/포인트**: 주문 시 자동 차감, 취소 시 자동 복원
- **사진 증빙**: 수거·세탁완료 시 Supabase Storage 업로드 필수
- **정산**: 건당 수수료 제외, 주 단위 자동 집계 (매주 월요일 01:00 KST)
- **CRM**: D+3 리마인드, VIP 프로모션, 금요일 Night 푸시 자동 발송

## 필수 환경변수 (GITHUB_SECRETS.md 참조)

```bash
# Vercel 환경변수 (sepang-api)
TOSS_CLIENT_KEY / TOSS_SECRET_KEY
NAVER_SENS_SERVICE_ID / NAVER_SENS_ACCESS_KEY / NAVER_SENS_SECRET_KEY / NAVER_SENS_SENDER

# GitHub Secrets
MONITOR_API_TOKEN   # SLA 감시용 서비스 토큰
SLACK_WEBHOOK_URL   # 배포/장애 알림 (선택)
```
