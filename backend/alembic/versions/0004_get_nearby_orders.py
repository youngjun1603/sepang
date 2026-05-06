"""PostGIS 반경 내 대기 주문 조회 함수

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-07
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION get_nearby_orders(p_shop_id UUID, p_radius_km INTEGER)
    RETURNS TABLE(
        order_id       UUID,
        wash_category  TEXT,
        service_type   TEXT,
        pickup_address TEXT,
        distance_m     FLOAT,
        deadline_at    TIMESTAMPTZ,
        total_amount   INTEGER
    ) AS $$
    BEGIN
        RETURN QUERY
        SELECT
            o.id,
            o.wash_category::TEXT,
            o.service_type::TEXT,
            o.pickup_address,
            ST_Distance(
                ST_Transform(o.pickup_location::geometry, 3857),
                ST_Transform(s.location::geometry,        3857)
            ),
            o.deadline_at,
            o.total_amount
        FROM orders o
        CROSS JOIN shops s
        WHERE s.id = p_shop_id
          AND o.status = 'PENDING'
          AND o.deadline_at > NOW()
          AND ST_DWithin(
              ST_Transform(o.pickup_location::geometry, 3857),
              ST_Transform(s.location::geometry,        3857),
              p_radius_km * 1000.0
          )
        ORDER BY 5;
    END;
    $$ LANGUAGE plpgsql STABLE;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS get_nearby_orders(UUID, INTEGER)")
