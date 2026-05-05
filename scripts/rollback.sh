#!/bin/bash
# ============================================================
# 긴급 롤백 스크립트
# 사용법: ./rollback.sh [staging|production] [image_tag]
# ============================================================
set -euo pipefail

ENV="${1:-staging}"
TARGET_TAG="${2:-}"
CLUSTER="sepang-$ENV"
AWS_REGION="ap-northeast-2"
ECR="$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com"

echo "🔄 세팡 긴급 롤백 시작 — 환경: $ENV"

# 이전 태스크 정의 버전 조회
get_prev_task_def() {
  SERVICE=$1
  aws ecs describe-services \
    --cluster "$CLUSTER" \
    --services "$SERVICE" \
    --query "services[0].taskDefinition" \
    --output text
}

# 특정 이미지 태그로 롤백
rollback_service() {
  SERVICE=$1
  CONTAINER=$2
  IMAGE="$ECR/sepang-api:$TARGET_TAG"

  echo "↩️  $SERVICE → $IMAGE"

  # 현재 태스크 정의 가져오기
  CURRENT_DEF=$(aws ecs describe-services \
    --cluster "$CLUSTER" \
    --services "$SERVICE" \
    --query "services[0].taskDefinition" \
    --output text)

  # 새 태스크 정의 등록 (이전 이미지로)
  NEW_DEF=$(aws ecs describe-task-definition \
    --task-definition "$CURRENT_DEF" \
    --query "taskDefinition" \
    --output json | \
    python3 -c "
import sys, json
td = json.load(sys.stdin)
for c in td['containerDefinitions']:
    if c['name'] == '$CONTAINER':
        c['image'] = '$IMAGE'
# 불필요 필드 제거
for key in ['taskDefinitionArn','revision','status','requiresAttributes','compatibilities','registeredAt','registeredBy']:
    td.pop(key, None)
print(json.dumps(td))
  " | aws ecs register-task-definition --cli-input-json file:///dev/stdin \
    --query "taskDefinition.taskDefinitionArn" --output text)

  # 서비스 업데이트
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$SERVICE" \
    --task-definition "$NEW_DEF" \
    --force-new-deployment

  echo "✅ $SERVICE 롤백 태스크 등록 완료"
}

if [ -z "$TARGET_TAG" ]; then
  # 태그 미지정 → 이전 리비전으로 롤백
  echo "⚠️  이미지 태그 미지정 — ECS 이전 리비전으로 롤백"
  for SERVICE in sepang-api-$ENV sepang-worker-$ENV; do
    CURRENT_REV=$(aws ecs describe-services \
      --cluster "$CLUSTER" \
      --services "$SERVICE" \
      --query "services[0].taskDefinition" \
      --output text | grep -o '[0-9]*$')
    PREV_REV=$((CURRENT_REV - 1))
    TASK_FAMILY="${SERVICE//-$ENV/}"
    aws ecs update-service \
      --cluster "$CLUSTER" \
      --service "$SERVICE" \
      --task-definition "$TASK_FAMILY:$PREV_REV" \
      --force-new-deployment
    echo "✅ $SERVICE → 리비전 $PREV_REV"
  done
else
  rollback_service "sepang-api-$ENV"    "api"
  rollback_service "sepang-worker-$ENV" "worker"
fi

echo ""
echo "⏳ 서비스 안정화 대기 (최대 3분)..."
aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services "sepang-api-$ENV"

echo "✅ 롤백 완료 — $(date)"

# 헬스 체크
BASE_URL="https://api${ENV != 'production' && echo '-staging' || echo ''}.sepang.kr"
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE_URL/health" || echo "000")
if [ "$STATUS" = "200" ]; then
  echo "✅ 헬스 체크 통과: $BASE_URL"
else
  echo "❌ 헬스 체크 실패: $BASE_URL (HTTP $STATUS)"
  exit 1
fi
