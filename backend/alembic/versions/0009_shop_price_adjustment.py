"""점주 가격 조정 — price_adj_settings + shops/orders 컬럼 추가

Revision ID: 0009
Revises: 0008
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. 전역 조정 허용 범위 설정 테이블 ─────────────────────────
    op.execute("""
        CREATE TABLE price_adj_settings (
            id          SERIAL PRIMARY KEY,
            min_rate    NUMERIC(5,4) NOT NULL DEFAULT -0.30,
            max_rate    NUMERIC(5,4) NOT NULL DEFAULT  0.20,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by  UUID REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    op.execute("INSERT INTO price_adj_settings (min_rate, max_rate) VALUES (-0.30, 0.20)")

    # ── 2. shops — 점주별 가격 조정률 컬럼 ─────────────────────────
    op.execute("ALTER TABLE shops ADD COLUMN IF NOT EXISTS price_adj_rate NUMERIC(5,4) NOT NULL DEFAULT 0.0")

    # ── 3. orders — 주문 시 적용된 조정률 기록 컬럼 ─────────────────
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shop_adj_rate NUMERIC(5,4) NOT NULL DEFAULT 0.0")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS shop_adj_amount INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("""
        ALTER TABLE orders
            DROP COLUMN IF EXISTS shop_adj_rate,
            DROP COLUMN IF EXISTS shop_adj_amount;

        ALTER TABLE shops
            DROP COLUMN IF EXISTS price_adj_rate;

        DROP TABLE IF EXISTS price_adj_settings;
    """)
