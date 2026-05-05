# 세팡 (SEPANG) — 운영 시스템

> 12시간 이내 수거·세탁·배송 완료 플랫폼

## 프로젝트 구조

```
sepang/
├── .github/workflows/          CI/CD 파이프라인 (6개)
│   ├── 01_ci.yml               테스트 + 린트 + 보안 스캔
│   ├── 02_cd_staging.yml       스테이징 자동 배포 (develop)
│   ├── 03_cd_production.yml    프로덕션 Blue/Green (main, 승인 필요)
│   ├── 04_monitoring.yml       헬스 체크 + SLA 감시 (5분 간격)
│   ├── 05_dependency_update.yml 주간 자동 업데이트
│   └── 06_pr_checks.yml        PR 품질 게이팅
│
├── backend/                    FastAPI 백엔드
│   ├── main.py                 앱 엔트리포인트
│   ├── tasks.py                Celery 비동기 작업
│   ├── database_schema.sql     PostgreSQL + PostGIS 스키마
│   ├── requirements.txt        Python 의존성
│   ├── alembic/                DB 마이그레이션
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 0001_initial_schema.py
│   │       └── 0002_seed_data.py
│   ├── app/
│   │   ├── core/               설정 + DB + 인증
│   │   ├── api/v1/             REST API 엔드포인트
│   │   │   ├── auth.py         OTP / 점주로그인 / 관리자2FA
│   │   │   └── orders.py       주문 CRUD + WebSocket
│   │   ├── services/           비즈니스 로직 서비스
│   │   └── ws/                 WebSocket 연결 관리
│   └── tests/
│       ├── unit/               단위 테스트 (DB 불필요)
│       └── integration/        통합 테스트 (PostgreSQL 필요)
│
├── frontend/
│   ├── shared/                 3개 앱 공유 코드
│   │   ├── lib/api-client.ts   API 클라이언트 + 타입
│   │   ├── hooks/              useAuth, useOrder
│   │   └── components/         TrackingScreen, PartnerTaskScreen
│   ├── customer/               고객 앱 (sepang.kr)
│   │   └── src/App.jsx         Next.js PWA
│   ├── partner/                점주 앱 (partner.sepang.kr)
│   │   └── src/App.jsx
│   └── admin/                  관리자 콘솔 (admin.internal.sepang.kr)
│       └── src/App.jsx
│
├── infra/
│   ├── docker/                 Dockerfile (API / Worker / Beat)
│   │   └── docker-compose.yml  로컬 개발 인프라
│   ├── nginx/nginx.conf        리버스 프록시 + VPN 격리
│   ├── terraform/              AWS IaC (VPC/RDS/Redis/S3/ECS)
│   └── ecs/                    ECS 태스크 정의 템플릿
│
└── scripts/
    ├── rollback.sh             긴급 롤백
    └── db_maintenance.sh       DB 유지보수

```

## 빠른 시작

```bash
# 1. 클론 & 환경변수 설정
git clone https://github.com/your-org/sepang.git
cd sepang
make setup           # .env 생성 + DB 초기화

# 2. 개발 서버
make dev             # FastAPI :8000 + DB + Redis

# 3. 테스트
make test

# 4. 린트
make lint
```

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| 고객 앱 | Next.js 14 PWA (sepang.kr) |
| 점주 앱 | Next.js 14 PWA (partner.sepang.kr) |
| 관리자 | Next.js 14 + VPN 전용 |
| Backend | FastAPI + SQLAlchemy + WebSocket |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Cache/Queue | Redis 7 + Celery |
| Storage | AWS S3 (증빙 사진) |
| Push | FCM + 카카오 알림톡 |
| Infra | AWS ECS Fargate + RDS + ElastiCache |
| IaC | Terraform 1.7 |
| CI/CD | GitHub Actions |

## 핵심 비즈니스 로직

- **SLA**: 주문 생성 즉시 `deadline_at = ordered_at + 12h` 자동 설정
- **Geo-fencing**: PostGIS `ST_DWithin`으로 반경 3km 점포 매칭
- **낙관적 잠금**: `accept_order()` DB 함수로 동시 수락 경쟁 방지
- **사진 증빙**: 수거·배송 완료 시 S3 업로드 필수
- **정산**: 건당 1,000원 수수료 제외, 주 단위 자동 집계
- **CRM**: Celery Beat 기반 자동 푸시 (D+3, VIP, 금요일)

## 배포 플로우

```
feature/* → develop   → CI 통과 → 스테이징 자동 배포
develop   → main (PR) → 운영팀 승인 → 프로덕션 Blue/Green
                                    → 스모크 실패 시 자동 롤백
```

## 필수 설정 (GITHUB_SECRETS.md 참조)

```bash
# GitHub Secrets 등록
AWS_ACCOUNT_ID / SLACK_WEBHOOK_URL / MONITOR_API_TOKEN ...

# AWS OIDC 설정 (장기 자격증명 없음)
aws iam create-open-id-connect-provider ...
```
