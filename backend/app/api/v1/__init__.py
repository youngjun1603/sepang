from fastapi import APIRouter
from app.api.v1.orders      import router as orders_router
from app.api.v1.auth        import router as auth_router
from app.api.v1.admin       import router as admin_router
from app.api.v1.users       import router as users_router
from app.api.v1.settlements import router as settlements_router
from app.api.v1.reviews     import router as reviews_router
from app.api.v1.geocoding   import router as geocoding_router

router = APIRouter()
router.include_router(auth_router,        tags=["auth"])
router.include_router(orders_router,      tags=["orders"])
router.include_router(admin_router,       tags=["admin"])
router.include_router(users_router,       tags=["users"])
router.include_router(settlements_router, tags=["settlements"])
router.include_router(reviews_router,     tags=["reviews"])
router.include_router(geocoding_router,   tags=["geocode"])

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/health/db")
async def health_db():
    from app.core.database import engine
    from sqlalchemy import text
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}

@router.get("/health/storage")
async def health_storage():
    """Supabase Storage 연결 확인"""
    from app.core.config import settings
    if not settings.SUPABASE_URL:
        return {"status": "skip", "storage": "not configured"}
    return {"status": "ok", "storage": "supabase"}
