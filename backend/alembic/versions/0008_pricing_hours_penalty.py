"""날씨·거리 요금, 매장 운영시간, 점주 패널티

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. 날씨 요금 설정 ───────────────────────────────────────
    op.execute("""
        CREATE TABLE weather_pricing (
            id          SERIAL PRIMARY KEY,
            condition   VARCHAR(20) NOT NULL UNIQUE,  -- RAIN | SNOW | RAIN_SNOW
            multiplier  NUMERIC(4,2) NOT NULL DEFAULT 1.0,
            is_active   BOOLEAN NOT NULL DEFAULT true,
            description TEXT,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by  UUID REFERENCES users(id) ON DELETE SET NULL
        );

        INSERT INTO weather_pricing (condition, multiplier, description) VALUES
            ('RAIN',      1.50, '비 오는 날 요금 1.5배'),
            ('SNOW',      2.00, '눈 오는 날 요금 2.0배'),
            ('RAIN_SNOW', 1.75, '비/눈 혼합 시 요금 1.75배');
    """)

    # ── 2. 거리 구간 요금 설정 ──────────────────────────────────
    op.execute("""
        CREATE TABLE distance_pricing (
            id          SERIAL PRIMARY KEY,
            min_km      NUMERIC(5,2) NOT NULL,
            max_km      NUMERIC(5,2),          -- NULL = 초과 구간 (이상)
            surcharge   INTEGER NOT NULL DEFAULT 0,
            is_active   BOOLEAN NOT NULL DEFAULT true,
            description TEXT,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by  UUID REFERENCES users(id) ON DELETE SET NULL
        );

        INSERT INTO distance_pricing (min_km, max_km, surcharge, description) VALUES
            (0,    1.0,  0,    '1km 이내 — 기본 요금'),
            (1.0,  2.0,  1000, '1~2km — +1,000원'),
            (2.0,  3.0,  2000, '2~3km — +2,000원'),
            (3.0,  NULL, 3000, '3km 초과 — +3,000원');
    """)

    # ── 3. 매장 운영 시간 ────────────────────────────────────────
    op.execute("""
        CREATE TABLE shop_hours (
            id           SERIAL PRIMARY KEY,
            shop_id      UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
            day_of_week  SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
            -- 0=월 1=화 2=수 3=목 4=금 5=토 6=일
            is_closed    BOOLEAN NOT NULL DEFAULT false,
            is_24h       BOOLEAN NOT NULL DEFAULT false,
            open_time    TIME,   -- is_24h=false, is_closed=false 일 때 사용
            close_time   TIME,
            UNIQUE (shop_id, day_of_week)
        );
    """)

    # ── 4. 점주 패널티 ──────────────────────────────────────────
    op.execute("""
        CREATE TABLE partner_penalties (
            id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            shop_id      UUID NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
            order_id     UUID REFERENCES orders(id) ON DELETE SET NULL,
            penalty_type VARCHAR(30) NOT NULL,
            -- LATE_ACCEPT: 수락 지연 | REJECTION: 거절 | NO_RESPONSE: 무응답
            penalty_point INTEGER NOT NULL DEFAULT 1,
            description  TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX idx_partner_penalties_shop ON partner_penalties(shop_id);
        CREATE INDEX idx_partner_penalties_created ON partner_penalties(created_at);
    """)

    # ── 5. shops 테이블 — 패널티 관련 컬럼 추가 ─────────────────
    op.execute("""
        ALTER TABLE shops
            ADD COLUMN IF NOT EXISTS penalty_score     INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS penalty_suspended BOOLEAN NOT NULL DEFAULT false;
    """)

    # ── 6. orders 테이블 — 날씨·거리 요금 컬럼 추가 ─────────────
    op.execute("""
        ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS weather_condition  VARCHAR(20),
            ADD COLUMN IF NOT EXISTS weather_multiplier NUMERIC(4,2) NOT NULL DEFAULT 1.0,
            ADD COLUMN IF NOT EXISTS distance_km        NUMERIC(6,3),
            ADD COLUMN IF NOT EXISTS distance_surcharge INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS rejected_at        TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS reject_reason      TEXT;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE orders
            DROP COLUMN IF EXISTS weather_condition,
            DROP COLUMN IF EXISTS weather_multiplier,
            DROP COLUMN IF EXISTS distance_km,
            DROP COLUMN IF EXISTS distance_surcharge,
            DROP COLUMN IF EXISTS rejected_at,
            DROP COLUMN IF EXISTS reject_reason;

        ALTER TABLE shops
            DROP COLUMN IF EXISTS penalty_score,
            DROP COLUMN IF EXISTS penalty_suspended;

        DROP TABLE IF EXISTS partner_penalties;
        DROP TABLE IF EXISTS shop_hours;
        DROP TABLE IF EXISTS distance_pricing;
        DROP TABLE IF EXISTS weather_pricing;
    """)
