# ============================================================
# 세팡 Makefile — 개발/배포 명령어 모음
# ============================================================

.PHONY: help setup dev test lint migrate deploy rollback

help:
	@echo "세팡 개발 명령어:"
	@echo "  make setup      — 개발 환경 초기 설정"
	@echo "  make dev        — 로컬 개발 서버 시작"
	@echo "  make test       — 전체 테스트 실행"
	@echo "  make lint       — 린트 + 타입 체크"
	@echo "  make migrate    — DB 마이그레이션 실행"
	@echo "  make deploy-staging — 스테이징 수동 배포"
	@echo "  make rollback   — 프로덕션 긴급 롤백"

setup:
	@echo "🔧 개발 환경 설정 중..."
	cp .env.example .env
	cd backend && pip install -r requirements.txt
	docker compose -f infra/docker/docker-compose.yml up -d postgres redis
	sleep 3
	cd backend && alembic upgrade head
	@echo "✅ 설정 완료. 'make dev'로 서버를 시작하세요."

dev:
	@echo "🚀 개발 서버 시작..."
	docker compose -f infra/docker/docker-compose.yml up -d postgres redis
	cd backend && uvicorn main:app --reload --port 8000

test:
	@echo "🧪 테스트 실행..."
	cd backend && pytest tests/unit/ -v
	cd backend && pytest tests/integration/ -v --tb=short

lint:
	@echo "🔍 린트 & 타입 체크..."
	cd backend && ruff check . && ruff format --check .
	cd backend && mypy app/ --ignore-missing-imports

migrate:
	@echo "🗄️  DB 마이그레이션..."
	cd backend && alembic upgrade head

migrate-down:
	cd backend && alembic downgrade -1

deploy-staging:
	@echo "📦 스테이징 배포..."
	gh workflow run 02_cd_staging.yml --ref develop

rollback:
	@echo "🔄 긴급 롤백..."
	./scripts/rollback.sh production

infra-plan:
	cd infra/terraform && terraform init && terraform plan \
		-var="db_password=$$DB_PASSWORD" \
		-var="jwt_secret=$$JWT_SECRET"

infra-apply:
	cd infra/terraform && terraform apply \
		-var="db_password=$$DB_PASSWORD" \
		-var="jwt_secret=$$JWT_SECRET"

docker-build:
	docker build -f infra/docker/Dockerfile.api -t sepang-api:local .
	docker build -f infra/docker/Dockerfile.worker -t sepang-worker:local .
