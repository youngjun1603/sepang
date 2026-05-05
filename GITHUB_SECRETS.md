# GitHub Secrets & Environment 설정 가이드

## Required Secrets

GitHub Repository → Settings → Secrets and variables → Actions

### AWS 인증 (OIDC — 장기 자격증명 없음)
```
AWS_ACCOUNT_ID          AWS 계정 ID (12자리 숫자)
```

### 데이터베이스
```
DB_PASSWORD             RDS 마스터 비밀번호
```

### 인프라
```
PRIVATE_SUBNET_IDS      스테이징 프라이빗 서브넷 ID (콤마 구분)
ECS_SECURITY_GROUP      스테이징 ECS 보안 그룹 ID
PROD_PRIVATE_SUBNET_IDS 프로덕션 프라이빗 서브넷 ID
PROD_ECS_SG             프로덕션 ECS 보안 그룹 ID
```

### 알림
```
SLACK_WEBHOOK_URL       Slack Incoming Webhook URL
```

### 모니터링
```
MONITOR_API_TOKEN       /api/v1/admin/* 조회용 서비스 토큰
BOT_TOKEN               GitHub Bot PAT (의존성 PR 생성용)
```

## GitHub Environments 설정

### staging
- Environment name: `staging`
- URL: `https://staging.sepang.kr`
- Protection rules: 없음 (자동 배포)

### production
- Environment name: `production`
- URL: `https://sepang.kr`
- Protection rules:
  - Required reviewers: 운영팀 최소 1명
  - Wait timer: 5분 (배포 전 냉각 시간)
  - Allowed branches: main only

## AWS IAM OIDC 설정

```bash
# GitHub OIDC Provider 등록
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1

# Staging 배포 Role
aws iam create-role \
  --role-name sepang-github-actions-staging \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Federated":"arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"},
      "Action":"sts:AssumeRoleWithWebIdentity",
      "Condition":{
        "StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com"},
        "StringLike":{"token.actions.githubusercontent.com:sub":"repo:your-org/sepang:ref:refs/heads/develop"}
      }
    }]
  }'
```

## 브랜치 전략 (Git Flow)

```
main ─────────────────────────────── 프로덕션 (승인 필요)
  └── release/v1.x ─────────────── RC 테스트
develop ─────────────────────────── 스테이징 자동 배포
  ├── feature/SL-001-order-api ─── 기능 개발
  ├── fix/SL-042-sla-timer ──────── 버그 수정
  └── hotfix/prod-crash ─────────── 긴급 수정 (main으로 직접 PR)
```

## 배포 플로우

```
feature/* → develop    → CI 통과 → 스테이징 자동 배포
develop   → main (PR)  → CI + 승인 → 프로덕션 Blue/Green 배포
                                   → 스모크 실패 시 자동 롤백
```
