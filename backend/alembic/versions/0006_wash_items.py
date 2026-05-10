"""add wash_items table + orders.wash_category ENUM → VARCHAR

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-10
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE wash_items (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            key         VARCHAR(50)  UNIQUE NOT NULL,
            label       VARCHAR(100) NOT NULL,
            icon        VARCHAR(10)  NOT NULL DEFAULT '🧺',
            base_price  INTEGER      NOT NULL,
            is_active   BOOLEAN      NOT NULL DEFAULT true,
            sort_order  INTEGER      NOT NULL DEFAULT 0,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )
    """)

    # 기존 4개 품목 시드 (고객 앱 하드코딩과 동일한 값)
    op.execute("""
        INSERT INTO wash_items (key, label, icon, base_price, sort_order) VALUES
            ('CLOTHES_30L', '생활빨래 30L', '🧺', 13000, 1),
            ('CLOTHES_50L', '생활빨래 50L', '🧺', 18000, 2),
            ('BLANKET',     '이불',         '🛏', 16000, 3),
            ('SHOES',       '운동화',       '👟', 10000, 4)
    """)

    # orders.wash_category: PostgreSQL ENUM → VARCHAR(50)
    # 기존 주문 데이터는 TEXT::wash_category 캐스트로 그대로 유지
    op.execute("""
        ALTER TABLE orders
        ALTER COLUMN wash_category TYPE VARCHAR(50)
        USING wash_category::TEXT
    """)


def downgrade():
    op.drop_table("wash_items")
    # wash_category를 ENUM으로 되돌리지 않음 (데이터 안전 우선)
