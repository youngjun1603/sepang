"""
세탁 품목 API
GET  /api/v1/wash-items/             공개 — 활성 품목 목록 (고객 앱용)
GET  /api/v1/wash-items/all          관리자 — 비활성 포함 전체 목록
POST /api/v1/wash-items/             관리자 — 품목 생성
PATCH /api/v1/wash-items/{item_id}   관리자 — 품목 수정 (가격/라벨/활성 등)
DELETE /api/v1/wash-items/{item_id}  관리자 — 품목 비활성화 (소프트 삭제)
"""
from __future__ import annotations
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.auth import require_role

router = APIRouter(prefix="/wash-items", tags=["wash-items"])

_ALLOWED_PATCH = {"label", "icon", "base_price", "is_active", "sort_order"}


# ── Schemas ───────────────────────────────────────────────────────────────────

class WashItemCreate(BaseModel):
    key:        str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Z0-9_]+$")
    label:      str = Field(..., min_length=2, max_length=100)
    icon:       str = Field("🧺", max_length=10)
    base_price: int = Field(..., ge=1000, le=500000)
    sort_order: int = Field(0, ge=0)


class WashItemUpdate(BaseModel):
    label:      Optional[str] = Field(None, min_length=2, max_length=100)
    icon:       Optional[str] = Field(None, max_length=10)
    base_price: Optional[int] = Field(None, ge=1000, le=500000)
    is_active:  Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_active_wash_items(db: AsyncSession = Depends(get_db)):
    """활성 품목만 반환 — 고객 앱에서 skipAuth로 호출"""
    rows = await db.execute(text("""
        SELECT id::text, key, label, icon, base_price, sort_order
        FROM wash_items
        WHERE is_active = true
        ORDER BY sort_order, created_at
    """))
    return [dict(r._mapping) for r in rows.fetchall()]


@router.get("/all")
async def list_all_wash_items(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    """비활성 포함 전체 — 관리자 전용"""
    rows = await db.execute(text("""
        SELECT id::text, key, label, icon, base_price, is_active, sort_order, created_at::text
        FROM wash_items
        ORDER BY sort_order, created_at
    """))
    return [dict(r._mapping) for r in rows.fetchall()]


@router.post("/", status_code=201)
async def create_wash_item(
    body: WashItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    dup = await db.execute(
        text("SELECT id FROM wash_items WHERE key = :key"), {"key": body.key}
    )
    if dup.fetchone():
        raise HTTPException(409, f"이미 존재하는 품목 키입니다: {body.key}")

    row = await db.execute(text("""
        INSERT INTO wash_items (key, label, icon, base_price, sort_order)
        VALUES (:key, :label, :icon, :price, :sort)
        RETURNING id::text, key, label, icon, base_price, sort_order
    """), {
        "key":   body.key,
        "label": body.label,
        "icon":  body.icon,
        "price": body.base_price,
        "sort":  body.sort_order,
    })
    await db.commit()
    return dict(row.fetchone()._mapping)


@router.patch("/{item_id}")
async def update_wash_item(
    item_id: UUID,
    body: WashItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()
               if k in _ALLOWED_PATCH}
    if not updates:
        raise HTTPException(400, "변경할 항목이 없습니다")

    set_clause = ", ".join(f"{col} = :{col}" for col in updates)
    updates["item_id"] = str(item_id)
    result = await db.execute(
        text(f"UPDATE wash_items SET {set_clause} WHERE id = :item_id RETURNING id"),
        updates,
    )
    if not result.fetchone():
        raise HTTPException(404, "품목을 찾을 수 없습니다")
    await db.commit()
    return {"success": True}


@router.delete("/{item_id}")
async def deactivate_wash_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role("ADMIN")),
):
    result = await db.execute(
        text("UPDATE wash_items SET is_active = false WHERE id = :id RETURNING id"),
        {"id": str(item_id)},
    )
    if not result.fetchone():
        raise HTTPException(404, "품목을 찾을 수 없습니다")
    await db.commit()
    return {"success": True}
