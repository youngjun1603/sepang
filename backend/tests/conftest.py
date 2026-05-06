"""pytest 전역 설정 — 세팡 테스트 스위트"""
import asyncio
import os
import sys
import pytest
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def db():
    """Integration test DB session against TEST_DATABASE_URL"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    engine = create_async_engine(db_url, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture(scope="module")
async def customer_user(db):
    from sqlalchemy import text
    user_id = "00000000-0000-0000-0000-000000000001"
    await db.execute(text("""
        INSERT INTO users (id, role, name, phone)
        VALUES (:id, 'CUSTOMER', 'Test Customer', '01011111111')
        ON CONFLICT (id) DO NOTHING
    """), {"id": user_id})
    await db.commit()
    return {"id": user_id, "role": "CUSTOMER"}


@pytest_asyncio.fixture(scope="module")
async def partner_user(db):
    from sqlalchemy import text
    user_id = "00000000-0000-0000-0000-000000000002"
    shop_id = "00000000-0000-0000-0000-000000000010"
    await db.execute(text("""
        INSERT INTO users (id, role, name, phone, business_number)
        VALUES (:id, 'PARTNER', 'Test Partner', '01022222222', '123-45-67890')
        ON CONFLICT (id) DO NOTHING
    """), {"id": user_id})
    await db.execute(text("""
        INSERT INTO shops (id, owner_id, name, address, location)
        VALUES (:shop_id, :owner_id, 'Test Shop', '강남구 테헤란로 1',
                ST_SetSRID(ST_MakePoint(127.030, 37.500), 4326))
        ON CONFLICT (id) DO NOTHING
    """), {"shop_id": shop_id, "owner_id": user_id})
    await db.commit()
    return {"id": user_id, "role": "PARTNER", "shop_id": shop_id}


@pytest_asyncio.fixture
async def client():
    from httpx import AsyncClient, ASGITransport
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


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
