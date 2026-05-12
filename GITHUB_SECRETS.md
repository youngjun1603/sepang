# GitHub Secrets & 환경변수 설정 가이드

## GitHub Repository Secrets

GitHub → youngjun1603/sepang → Settings → Secrets and variables → Actions

### Vercel 배포
```
VERCEL_TOKEN                  Vercel Personal Access Token
VERCEL_ORG_ID                 team_JBhMZkd4FWWdIinWku39uvFQ
VERCEL_PROJECT_ID_BACKEND     prj_2pECSbwJ4BMy4iM7R9mp2XI1XSSc
VERCEL_PROJECT_ID_CUSTOMER    prj_q9hn6s3gExBIBH5xckqSgvKHVBWv
VERCEL_PROJECT_ID_PARTNER     prj_Ynt1tle9JFSmwm3A1T3dLJwOAY6v
VERCEL_PROJECT_ID_ADMIN       prj_q40A5Llde4FWxYnal6JHNVWO5Hj0
```

### Supabase
```
SUPABASE_DIRECT_URL           postgresql+asyncpg://postgres:***@db.apghgbecayjfsuswaggf.supabase.co:5432/postgres
                              (마이그레이션 전용 — Direct Connection)
SUPABASE_PROJECT_REF          apghgbecayjfsuswaggf
SUPABASE_ACCESS_TOKEN         Supabase Management API 토큰
SUPABASE_URL                  https://apghgbecayjfsuswaggf.supabase.co
SUPABASE_ANON_KEY             Supabase anon public key
```

### 모니터링·알림
```
MONITOR_API_TOKEN             SLA 감시용 정적 토큰 (Vercel sepang-api와 동일값)
SLACK_WEBHOOK_URL             Slack Incoming Webhook (없어도 배포 계속됨)
```

---

## Vercel 환경변수 — sepang-api

Vercel 대시보드 → sepang-api → Settings → Environment Variables

### 필수 (현재 미설정 — 서비스 불가)
```
TOSS_CLIENT_KEY               토스페이먼츠 클라이언트 키 (live_ck_... 또는 test_ck_...)
TOSS_SECRET_KEY               토스페이먼츠 시크릿 키 (live_sk_... 또는 test_sk_...)
NAVER_SENS_SERVICE_ID         NAVER Cloud SMS 프로젝트 Service ID
NAVER_SENS_ACCESS_KEY         NAVER Cloud Access Key ID
NAVER_SENS_SECRET_KEY         NAVER Cloud Secret Key
NAVER_SENS_SENDER             인증된 발신번호 (하이픈 없이, 예: 01012345678)
```

### 설정 완료
```
DATABASE_URL                  postgresql+asyncpg://...@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres
JWT_SECRET                    ✅
ENVIRONMENT                   production
SUPABASE_URL                  https://apghgbecayjfsuswaggf.supabase.co
SUPABASE_ANON_KEY             ✅
SUPABASE_SERVICE_ROLE_KEY     ✅
MONITOR_API_TOKEN             ✅
FCM_SERVICE_ACCOUNT_JSON      ✅ (Firebase Admin SDK 서비스 계정)
VAPID_PRIVATE_KEY             ✅ (Web Push)
VAPID_PUBLIC_KEY              ✅
KAKAO_MAP_REST_API_KEY        ✅
```

---

## Vercel 환경변수 — 프론트엔드 3개 프로젝트

sepang-customer / sepang-partner / sepang-admin 공통

```
NEXT_PUBLIC_SUPABASE_URL      https://apghgbecayjfsuswaggf.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY ✅
NEXT_PUBLIC_API_URL           https://api.sepang.kr
NEXT_PUBLIC_VAPID_PUBLIC_KEY  ✅ (Web Push — customer·partner만 해당)
```

---

## 서비스 URL (도메인 연동 완료)

| 앱 | URL | Vercel 프로젝트 |
|----|-----|----------------|
| 고객 앱 | https://sepang.kr | sepang-customer |
| 점주 앱 | https://partner.sepang.kr | sepang-partner |
| 관리자 콘솔 | https://admin.sepang.kr | sepang-admin |
| API | https://api.sepang.kr | sepang-api |

---

## 배포 플로우

```
feature/* → develop    →  CI (lint·test) 통과  →  Vercel Preview 자동 배포
develop   → main (PR)  →  DB 마이그레이션       →  Vercel Production 배포
                       →  Edge Functions 배포   →  스모크 테스트
```

## 브랜치 전략

```
main ──────────────────────── 프로덕션 (직접 push 지양, PR 권장)
  └── develop ──────────────── 스테이징 (Preview 배포)
        ├── feature/SL-001    기능 개발
        ├── fix/SL-042        버그 수정
        └── hotfix/prod-crash 긴급 수정 (main으로 직접 PR)
```

---

## 외부 서비스 발급 필요 항목

### Toss Payments
1. https://developers.tosspayments.com 접속
2. 내 개발 정보 → API 키 발급
3. `TOSS_CLIENT_KEY`, `TOSS_SECRET_KEY` → Vercel sepang-api 환경변수 등록

### NAVER SENS (SMS)
1. https://console.ncloud.com → Simple & Easy Notification Service
2. 프로젝트 생성 → 발신번호 인증
3. 4종 키 → Vercel sepang-api 환경변수 등록
