"""P1: order cancellation improvements + partner availability

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-10
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    # orders.points_used — 취소 시 정확한 포인트 환불액 추적
    op.execute("ALTER TABLE orders ADD COLUMN points_used INTEGER NOT NULL DEFAULT 0")

    # wash_category ENUM 타입 제거 (0006에서 컬럼을 VARCHAR(50)로 이미 변환됨)
    op.execute("DROP TYPE IF EXISTS wash_category")


def downgrade():
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS points_used")
    # ENUM 타입은 복원하지 않음 (데이터 안전 우선)
