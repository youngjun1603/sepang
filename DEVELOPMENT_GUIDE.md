# 세팡 전체 개발 가이드

## 프로젝트 구조

```
sepang-full/
├── alembic/                  # DB 마이그레이션
│   ├── env.py
│   └── versions/
│       ├── 0001_initial_schema.py   # 전체 스키마
│       └── 0002_seed_data.py        # 초기 데이터
├── app/                      # FastAPI 앱 (이전 단계 파일)
│   ├── core/
│   ├── models/
│   ├── api/v1/
│   └── services/
├── frontend/                 # Next.js 공유 레이어
│   ├── lib/api-client.ts     # API 클라이언트 (타입 포함)
│   ├── hooks/
│   │   ├── useAuth.ts        # 인증 상태 훅
│   │   └── useOrder.ts       # 주문/추적/사진 훅
│   └── components/
│       ├── TrackingScreen.tsx     # 고객 실시간 추적
│       └── PartnerTaskScreen.tsx  # 점주 작업 화면
├── tests/
│   ├── conftest.py           # 공통 픽스처
│   ├── unit/
│   │   └── test_order_logic.py    # 비즈니스 로직 단위 테스트
│   └── integration/
│       ├── test_order_api.py      # API 통합 테스트
│       └── test_celery_tasks.py   # Celery 태스크 테스트
└── terraform/                # AWS 인프라 IaC
    ├── main.tf
    ├── variables.tf
    └── modules/
        ├── vpc/    ECS, RDS, Redis 격리 네트워크
        ├── rds/    PostgreSQL + PostGIS
        ├── redis/  ElastiCache 클러스터
        ├── s3/     사진 증빙 버킷
        └── ecs/    Fargate + ALB + Auto Scaling
```

## 단계별 실행

### 5단계: DB 마이그레이션
```bash
pip install alembic geoalchemy2 asyncpg psycopg2-binary
cd sepang-full

# 마이그레이션 실행
alembic upgrade head

# 롤백
alembic downgrade -1

# 현재 버전 확인
alembic current
```

### 4단계: Next.js 연동
```bash
# frontend/lib/api-client.ts를 각 앱으로 복사
cp frontend/lib/api-client.ts ../sepang-customer/src/lib/
cp frontend/lib/api-client.ts ../sepang-partner/src/lib/
cp frontend/lib/api-client.ts ../sepang-admin/src/lib/

# 환경변수 설정
echo "NEXT_PUBLIC_API_URL=https://api.sepang.kr" >> .env.local

# 기존 mock Context → API 훅으로 교체
# AuthProvider → useAuth 훅 사용
# 하드코딩 데이터 → orderApi.list(), orderApi.nearbyOrders() 등
```

### 테스트 실행
```bash
pip install pytest pytest-asyncio httpx pyjwt

# 단위 테스트 (DB 불필요)
pytest tests/unit/ -v

# 통합 테스트 (테스트 DB 필요)
export TEST_DATABASE_URL="postgresql+asyncpg://sepang:pw@localhost:5432/sepang_test"
pytest tests/integration/ -v

# 전체
pytest -v --tb=short
```

### 6단계: AWS 인프라
```bash
cd terraform

# 초기화
terraform init

# 플랜 확인
terraform plan \
  -var="db_password=$DB_PASSWORD" \
  -var="jwt_secret=$JWT_SECRET"

# 스테이징 배포
terraform workspace new staging
terraform apply -var-file="envs/staging/terraform.tfvars"

# 프로덕션
terraform workspace select production
terraform apply -var-file="envs/production/terraform.tfvars"
```

## 핵심 API → 훅 매핑

| 기존 mock | 실제 API 훅 |
|-----------|------------|
| `useState(POOL)` | `useNearbyOrders()` |
| `useState(countdown)` | `useOrderTracking(id).timeLeft` |
| `navigate("/tracking")` | WebSocket 자동 연결 |
| `setPhotos({pickup:true})` | `usePhotoUpload(id).upload()` |
| `login({ name, shopName })` | `authApi.partnerLogin()` |

## AWS 리소스 요약

| 리소스 | Staging | Production |
|--------|---------|------------|
| ECS CPU | 512 vCPU | 2048 vCPU |
| ECS RAM | 1 GB | 4 GB |
| RDS | db.t4g.small | db.r7g.large (Multi-AZ) |
| Redis | cache.t4g.small | cache.r7g.large (Multi-AZ) |
| ALB | 1개 | 1개 |
| ECS Tasks | 최소 1개 | 최소 2개, 최대 10개 |
