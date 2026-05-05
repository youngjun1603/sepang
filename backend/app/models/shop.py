"""Shop SQLAlchemy 모델"""
from __future__ import annotations
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Numeric, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.base import Base


class Shop(Base):
    __tablename__ = "shops"

    id:           Mapped[UUID]    = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id:     Mapped[UUID]    = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name:         Mapped[str]     = mapped_column(String(100), nullable=False)
    address:      Mapped[str]     = mapped_column(String(300), nullable=False)
    # location: Geography — geoalchemy2로 관리하므로 SQLAlchemy 매핑 생략
    team_type:    Mapped[str]     = mapped_column(String(10), nullable=False, default="DAY")
    radius_km:    Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False, default=Decimal("3.0"))
    rating:       Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("5.0"))
    review_count: Mapped[int]     = mapped_column(Integer, nullable=False, default=0)
    is_active:    Mapped[bool]    = mapped_column(Boolean, nullable=False, default=True)
    is_available: Mapped[bool]    = mapped_column(Boolean, nullable=False, default=False)
    bank_name:    Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bank_account: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    bank_holder:  Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
