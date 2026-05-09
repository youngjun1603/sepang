"""DB 연결 — SQLAlchemy 비동기"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Vercel Serverless + Supabase Transaction Pooler 조합:
# NullPool — 요청마다 새 커넥션, 완료 후 즉시 반환 (prepared statement 충돌 방지)
engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=settings.DEBUG,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

def sync_session_factory():
    """Celery 태스크용 동기 세션"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "+psycopg2")
    sync_engine = create_engine(sync_url)
    return sessionmaker(bind=sync_engine)()
