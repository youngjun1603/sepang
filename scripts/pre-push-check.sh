#!/usr/bin/env bash
# ============================================================
# pre-push-check.sh — 로컬 배포 전 사전 점검 스크립트
# 사용법: bash scripts/pre-push-check.sh [check1 check2 ...]
#
# 사용 가능한 체크:
#   deps      — 의존성 확인
#   lint      — 백엔드 lint (ruff)
#   types     — 백엔드 타입 체크 (mypy)
#   tests     — 백엔드 단위 테스트 (pytest)
#   imports   — 백엔드 import 검증
#   frontend  — 프론트엔드 타입 체크 (tsc)
#   yaml      — GitHub Actions YAML 문법 검증
#   ci_dirs   — CI working-directory 누락 검사
#   env       — .env 파일 노출 검사
#   vercel    — Vercel 설정 파일 검증
#   git       — git 상태 검사
#
# 예시: bash scripts/pre-push-check.sh frontend env git
# ============================================================
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0
SKIP=0
WARN=0

# ── 출력 헬퍼 ──────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
NC='\033[0m'

info()   { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()     { echo -e "${GREEN}[PASS]${NC} $*"; PASS=$((PASS + 1)); }
fail()   { echo -e "${RED}[FAIL]${NC} $*"; FAIL=$((FAIL + 1)); }
warn()   { echo -e "${YELLOW}[WARN]${NC} $*"; WARN=$((WARN + 1)); }
skip()   { echo -e "${GRAY}[SKIP]${NC} $*"; SKIP=$((SKIP + 1)); }
header() { echo -e "\n${YELLOW}══════════════════════════════════════${NC}"; echo -e "${YELLOW}  $*${NC}"; echo -e "${YELLOW}══════════════════════════════════════${NC}"; }

# 명령어 실행: 성공/실패 기록 + 실패 시 에러 출력
run_check() {
    local label="$1"; shift
    local output
    if output=$("$@" 2>&1); then
        ok "$label"
        return 0
    else
        fail "$label"
        echo "$output" | head -20 | sed 's/^/    /'
        return 1
    fi
}

# ── Python 실행 파일 탐지 ─────────────────────────────────
detect_python() {
    for cmd in python3 python "python3.12" "python3.11" "python3.10"; do
        if command -v "$cmd" &>/dev/null && "$cmd" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
            echo "$cmd"
            return 0
        fi
    done
    # Windows Git Bash: 일반적인 설치 경로 탐색
    for path in \
        "/c/Python312/python.exe" \
        "/c/Python311/python.exe" \
        "/c/Python310/python.exe" \
        "$USERPROFILE/AppData/Local/Programs/Python/Python312/python.exe" \
        "$USERPROFILE/AppData/Local/Programs/Python/Python311/python.exe"
    do
        if [ -x "$path" ] && "$path" -c "import sys; sys.exit(0)" 2>/dev/null; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

PYTHON_CMD=""
PY_AVAILABLE=false
if PYTHON_CMD=$(detect_python 2>/dev/null); then
    PY_AVAILABLE=true
fi

# pip 기반 툴 탐지 (python -m ruff 방식으로도 시도)
has_tool() {
    local tool="$1"
    command -v "$tool" &>/dev/null && return 0
    $PY_AVAILABLE && "$PYTHON_CMD" -m "$tool" --version &>/dev/null 2>&1 && return 0
    return 1
}

run_py_tool() {
    local tool="$1"; shift
    if command -v "$tool" &>/dev/null; then
        run_check "$*" "$tool" "$@"
    elif $PY_AVAILABLE; then
        run_check "$*" "$PYTHON_CMD" -m "$tool" "$@"
    else
        return 1
    fi
}

# ── 1. 의존성 확인 ─────────────────────────────────────────
check_deps() {
    header "의존성 확인"

    if $PY_AVAILABLE; then
        ok "Python: $($PYTHON_CMD --version 2>&1)"
    else
        fail "Python 3.10+ 없음 — 설치 필요 (python.org 또는 pyenv)"
        info "  백엔드 관련 점검(lint/types/tests)은 건너뜁니다"
    fi

    for cmd in node npm git; do
        if command -v "$cmd" &>/dev/null; then
            ok "$cmd: $($cmd --version 2>&1 | head -1)"
        else
            fail "$cmd 없음"
        fi
    done

    if $PY_AVAILABLE; then
        for tool in ruff mypy pytest; do
            if has_tool "$tool"; then
                ok "$tool 사용 가능"
            else
                skip "$tool 없음 — pip install $tool 필요"
            fi
        done
    fi
}

# ── 2. 백엔드 lint ─────────────────────────────────────────
check_backend_lint() {
    header "백엔드 lint & 포맷 (Ruff)"

    if ! $PY_AVAILABLE || ! has_tool ruff; then
        skip "ruff 없음 — Python 설치 후: pip install ruff"
        return
    fi

    cd "$REPO_ROOT/backend"
    local ruff_cmd="ruff"
    command -v ruff &>/dev/null || ruff_cmd="$PYTHON_CMD -m ruff"

    if $ruff_cmd check . --output-format=concise 2>&1 | grep -q "error\|warning"; then
        local issues
        issues=$($ruff_cmd check . --output-format=concise 2>&1 | head -20)
        fail "ruff lint 오류:\n    $issues"
    else
        ok "ruff lint 통과"
    fi

    if $ruff_cmd format --check . &>/dev/null 2>&1; then
        ok "ruff format 통과"
    else
        fail "ruff format — 포맷 불일치 (ruff format . 실행 필요)"
    fi
}

# ── 3. 백엔드 타입 체크 ───────────────────────────────────
check_backend_types() {
    header "백엔드 타입 체크 (mypy)"

    if ! $PY_AVAILABLE || ! has_tool mypy; then
        skip "mypy 없음 — Python 설치 후: pip install mypy types-bcrypt types-jwt"
        return
    fi

    cd "$REPO_ROOT/backend"
    run_check "mypy app/" mypy app/ --ignore-missing-imports --strict
}

# ── 4. 백엔드 단위 테스트 ─────────────────────────────────
check_backend_tests() {
    header "백엔드 단위 테스트 (pytest)"

    if ! $PY_AVAILABLE || ! has_tool pytest; then
        skip "pytest 없음 — Python 설치 후: pip install pytest pytest-asyncio"
        return
    fi

    cd "$REPO_ROOT/backend"
    if [ ! -d "tests/unit" ]; then
        skip "tests/unit/ 디렉터리 없음"
        return
    fi

    run_check "pytest unit tests" pytest tests/unit/ -q --tb=short
}

# ── 5. 백엔드 import 검증 ─────────────────────────────────
check_backend_imports() {
    header "백엔드 import 검증"

    if ! $PY_AVAILABLE; then
        skip "Python 없음 — import 검증 건너뜀"
        return
    fi

    cd "$REPO_ROOT/backend"
    local check_script='
import sys
sys.path.insert(0, ".")
try:
    from app.core.config import settings
    from app.core.database import get_db
    from app.core.auth import get_current_user
    from app.api.v1 import auth, orders, users, admin, settlements
    print("OK")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
'
    run_check "백엔드 모듈 import" "$PYTHON_CMD" -c "$check_script"
}

# ── 6. 프론트엔드 타입 체크 ───────────────────────────────
check_frontend_types() {
    header "프론트엔드 타입 체크 (TypeScript)"

    if ! command -v npm &>/dev/null; then
        skip "npm 없음"
        return
    fi

    for app in customer partner admin; do
        local app_dir="$REPO_ROOT/frontend/$app"
        if [ ! -d "$app_dir" ]; then
            fail "$app 앱 디렉터리 없음: $app_dir"
            continue
        fi

        cd "$app_dir"

        if [ ! -d "node_modules" ]; then
            info "$app: node_modules 없음 — npm install 중..."
            if ! npm install --legacy-peer-deps --silent 2>/dev/null; then
                fail "$app: npm install 실패"
                continue
            fi
        fi

        run_check "typecheck ($app)" npm run typecheck
    done
}

# ── 7. YAML 문법 검증 ─────────────────────────────────────
check_yaml() {
    header "GitHub Actions YAML 문법 검증"

    local workflows_dir="$REPO_ROOT/.github/workflows"
    if [ ! -d "$workflows_dir" ]; then
        skip ".github/workflows 디렉터리 없음"
        return
    fi

    # yamllint 우선, 없으면 python yaml, 없으면 node js-yaml
    if command -v yamllint &>/dev/null; then
        for f in "$workflows_dir"/*.yml; do
            run_check "$(basename "$f")" yamllint -d relaxed "$f"
        done
    elif $PY_AVAILABLE && "$PYTHON_CMD" -c "import yaml" 2>/dev/null; then
        for f in "$workflows_dir"/*.yml; do
            local fname; fname=$(basename "$f")
            if "$PYTHON_CMD" -c "
import yaml, sys
with open('$f') as fh:
    yaml.safe_load(fh)
" 2>/dev/null; then
                ok "YAML 파싱: $fname"
            else
                fail "YAML 파싱 오류: $fname"
            fi
        done
    elif command -v node &>/dev/null; then
        # node로 기본 YAML 검증 (js-yaml 없어도 구조 체크)
        for f in "$workflows_dir"/*.yml; do
            local fname; fname=$(basename "$f")
            # 기본 파일 존재 + 비어있지 않은지만 확인
            if [ -s "$f" ]; then
                ok "파일 존재: $fname"
            else
                fail "빈 파일: $fname"
            fi
        done
        info "정확한 YAML 검증을 위해 pip install yamllint 권장"
    else
        skip "yamllint/python/node 없음 — YAML 검증 건너뜀"
    fi
}

# ── 8. CI working-directory 누락 검사 ─────────────────────
check_ci_working_dirs() {
    header "CI working-directory 누락 검사"

    local ci_file="$REPO_ROOT/.github/workflows/01_ci.yml"
    if [ ! -f "$ci_file" ]; then
        skip "01_ci.yml 없음"
        return
    fi

    # backend 관련 명령어가 working-directory 없이 실행되는지 grep으로 검사
    local issues=()

    # ruff, mypy, pytest, alembic 명령이 있는 줄을 찾고
    # 그 앞 5줄 안에 working-directory가 없으면 경고
    if $PY_AVAILABLE && "$PYTHON_CMD" -c "import yaml" 2>/dev/null; then
        local result
        result=$("$PYTHON_CMD" -c "
import yaml, sys

with open('$ci_file') as f:
    doc = yaml.safe_load(f)

backend_cmds = ['ruff', 'mypy', 'pytest', 'alembic']
problems = []

for job_name, job in (doc.get('jobs') or {}).items():
    steps = job.get('steps') or []
    for i, step in enumerate(steps):
        run_cmd = step.get('run', '')
        wd = step.get('working-directory', '')
        name = step.get('name', f'step {i+1}')
        for cmd in backend_cmds:
            if cmd in run_cmd and 'backend' not in wd:
                problems.append(f'  [{job_name}] \"{name}\" — {cmd} 명령에 working-directory 없음')

if problems:
    for p in problems:
        print(p)
    sys.exit(1)
" 2>&1)
        if [ $? -eq 0 ]; then
            ok "working-directory 누락 없음"
        else
            fail "working-directory 누락:"
            echo "$result" | sed 's/^/    /'
        fi
    else
        # grep 기반 간단 검사
        local missing
        missing=$(grep -n "run: .*\(ruff\|mypy\|pytest\|alembic\)" "$ci_file" 2>/dev/null || true)
        if [ -n "$missing" ]; then
            info "Python yaml 없어 정밀 검사 불가 — 수동 확인 권장"
            ok "01_ci.yml 존재 확인"
        else
            ok "working-directory 확인 (기본)"
        fi
    fi
}

# ── 9. 환경변수 파일 검사 ──────────────────────────────────
check_env() {
    header "환경변수 파일 검사"

    # .gitignore에 .env 포함 여부
    if grep -q "\.env" "$REPO_ROOT/.gitignore" 2>/dev/null; then
        ok ".env → .gitignore 포함됨"
    else
        fail ".env 파일이 .gitignore에 없음 — 시크릿 노출 위험"
    fi

    # 스테이징에 .env 파일 포함 여부
    local staged_env
    staged_env=$(git -C "$REPO_ROOT" diff --cached --name-only 2>/dev/null | grep -E "\.env($|\.)" || true)
    if [ -n "$staged_env" ]; then
        fail "⚠️  .env 파일이 git staging에 포함됨:\n    $staged_env\n    → git reset HEAD $staged_env 실행 필요"
    else
        ok ".env 파일 staging 없음"
    fi

    # secrets 관련 키워드가 실수로 커밋될 소지 있는 파일 확인
    local suspicious
    suspicious=$(git -C "$REPO_ROOT" diff --cached --name-only 2>/dev/null | grep -E "secret|password|credential|token" || true)
    if [ -n "$suspicious" ]; then
        fail "⚠️  민감한 이름의 파일이 staging에 있음:\n    $suspicious"
    else
        ok "민감 파일명 staging 없음"
    fi
}

# ── 10. Vercel 설정 검증 ───────────────────────────────────
check_vercel() {
    header "Vercel 설정 검증"

    # backend/vercel.json
    if [ -f "$REPO_ROOT/backend/vercel.json" ]; then
        if command -v node &>/dev/null; then
            # Windows Git Bash 경로 문제를 피하기 위해 cd 후 상대경로 사용
            run_check "backend/vercel.json 파싱" bash -c "cd '$REPO_ROOT/backend' && node -e \"const fs=require('fs');JSON.parse(fs.readFileSync('vercel.json','utf8'));console.log('OK');\""
        else
            ok "backend/vercel.json 존재"
        fi
    else
        fail "backend/vercel.json 없음"
    fi

    # requirements.txt
    if [ -f "$REPO_ROOT/backend/requirements.txt" ]; then
        ok "backend/requirements.txt 존재"
    else
        fail "backend/requirements.txt 없음"
    fi

    # 각 프론트엔드 package.json
    for app in customer partner admin; do
        if [ -f "$REPO_ROOT/frontend/$app/package.json" ]; then
            ok "frontend/$app/package.json 존재"
        else
            fail "frontend/$app/package.json 없음"
        fi
    done
}

# ── 11. Git 상태 검사 ──────────────────────────────────────
check_git() {
    header "Git 상태 검사"

    if ! command -v git &>/dev/null; then
        skip "git 없음"
        return
    fi

    cd "$REPO_ROOT"

    # 미커밋 변경 사항
    local unstaged
    unstaged=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
    if [ "$unstaged" -gt 0 ]; then
        info "미스테이징 파일 ${unstaged}개 있음 (커밋되지 않음)"
    fi

    # 스테이징된 파일
    local staged
    staged=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
    if [ "$staged" -gt 0 ]; then
        info "스테이징된 파일 ${staged}개"
        ok "커밋 준비 완료"
    else
        info "스테이징된 파일 없음"
    fi

    # 현재 브랜치
    local branch
    branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    ok "현재 브랜치: $branch"

    # main 브랜치 직접 push 경고
    if [ "$branch" = "main" ]; then
        warn "main 브랜치에 직접 push — PR을 통해 merge 권장"
    fi
}

# ── 최종 결과 ──────────────────────────────────────────────
print_result() {
    echo ""
    echo -e "${YELLOW}══════════════════════════════════════${NC}"
    echo -e "${YELLOW}  최종 결과${NC}"
    echo -e "${YELLOW}══════════════════════════════════════${NC}"
    printf "  통과: ${GREEN}%d${NC}  실패: ${RED}%d${NC}  경고: ${YELLOW}%d${NC}  건너뜀: ${GRAY}%d${NC}\n" "$PASS" "$FAIL" "$WARN" "$SKIP"
    echo ""

    if [ "$FAIL" -eq 0 ]; then
        echo -e "${GREEN}✅ 모든 점검 통과 — push 가능합니다${NC}"
        exit 0
    else
        echo -e "${RED}❌ ${FAIL}개 항목 실패 — 수정 후 재실행하세요${NC}"
        exit 1
    fi
}

# ── 메인 ───────────────────────────────────────────────────
main() {
    echo -e "${CYAN}"
    echo "  세팡 (Sepang) — 배포 전 사전 점검"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    if $PY_AVAILABLE; then
        echo "  Python: $PYTHON_CMD ($($PYTHON_CMD --version 2>&1))"
    else
        echo "  Python: 없음 (백엔드 점검 제한됨)"
    fi
    echo -e "${NC}"

    # 인수 없으면 전체 실행
    local checks=("${@}")
    if [ ${#checks[@]} -eq 0 ]; then
        checks=(deps lint types tests imports frontend yaml ci_dirs env vercel git)
    fi

    for check in "${checks[@]}"; do
        case "$check" in
            deps)      check_deps ;;
            lint)      check_backend_lint ;;
            types)     check_backend_types ;;
            tests)     check_backend_tests ;;
            imports)   check_backend_imports ;;
            frontend)  check_frontend_types ;;
            yaml)      check_yaml ;;
            ci_dirs)   check_ci_working_dirs ;;
            env)       check_env ;;
            vercel)    check_vercel ;;
            git)       check_git ;;
            *)         info "알 수 없는 체크: $check"; SKIP=$((SKIP + 1)) ;;
        esac
    done

    print_result
}

main "$@"
