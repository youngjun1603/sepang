"""주문 SQLAlchemy 모델 + 상태 Enum"""
from __future__ import annotations
import enum
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Numeric, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as PG_ENUM

from app.models.base import Base


class OrderStatus(str, enum.Enum):
    PENDING         = "PENDING"
    ACCEPTED        = "ACCEPTED"
    PICKUP_EN_ROUTE = "PICKUP_EN_ROUTE"
    PICKED_UP       = "PICKED_UP"
    WASHING         = "WASHING"
    DRYING          = "DRYING"
    DELIVERING      = "DELIVERING"
    COMPLETED       = "COMPLETED"
    CANCELLED       = "CANCELLED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id:      Mapped[UUID]   = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    shop_id:          Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status:           Mapped[str]    = mapped_column(String(32), default=OrderStatus.PENDING.value, nullable=False)
    service_type:     Mapped[str]    = mapped_column(String(8),  nullable=False)   # DAY | NIGHT
    wash_category:    Mapped[str]    = mapped_column(String(32), nullable=False)
    pickup_address:   Mapped[str]    = mapped_column(Text, nullable=False)
    pickup_lat:       Mapped[float]  = mapped_column(Numeric(9, 6), nullable=False)
    pickup_lng:       Mapped[float]  = mapped_column(Numeric(9, 6), nullable=False)
    delivery_address: Mapped[str]    = mapped_column(Text, nullable=False)
    delivery_lat:     Mapped[float]  = mapped_column(Numeric(9, 6), nullable=False)
    delivery_lng:     Mapped[float]  = mapped_column(Numeric(9, 6), nullable=False)
    total_amount:     Mapped[int]    = mapped_column(nullable=False)
    platform_fee:     Mapped[int]    = mapped_column(nullable=False, default=1000)
    customer_note:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ordered_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deadline_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at:     Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
