"""pytest 전역 설정 — 세팡 테스트 스위트"""
import asyncio
import os
import sys
import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# event_loop scope 설정
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def make_auth_header():
    """JWT 헤더 생성 픽스처 (테스트 전용 시크릿)"""
    def _make(user_id: str, role: str) -> dict:
        import jwt
        from datetime import datetime, timezone, timedelta
        token = jwt.encode(
            {"sub": user_id, "role": role,
             "exp": datetime.now(timezone.utc) + timedelta(hours=1),
             "type": "access"},
            "test-secret-key",
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}
    return _make
