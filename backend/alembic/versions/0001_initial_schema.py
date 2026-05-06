"""Initial schema — PostgreSQL + PostGIS

Revision ID: 0001
Revises:
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geography

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 확장
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "postgis"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # ENUMs — idempotent (DO block catches duplicate_object)
    for name, values in [
        ("user_role",         "CUSTOMER,PARTNER,ADMIN"),
        ("service_type",      "DAY,NIGHT"),
        ("team_type",         "DAY,NIGHT,BOTH"),
        ("order_status",      "PENDING,ACCEPTED,PICKED_UP,WASHING,DRYING,DELIVERING,COMPLETED,CANCELLED"),
        ("photo_type",        "PICKUP,DELIVERY,ISSUE"),
        ("settlement_status", "PENDING,PROCESSING,COMPLETED,FAILED"),
        ("notification_type", "FCM,KAKAO,SMS"),
        ("crm_status",        "WAITING,SCHEDULED,SENT,FAILED"),
        ("wash_category",     "CLOTHES_30L,CLOTHES_50L,BLANKET,SHOES"),
    ]:
        vals = ",".join(f"'{v}'" for v in values.split(","))
        op.execute(f"""
            DO $$ BEGIN
                CREATE TYPE {name} AS ENUM ({vals});
            EXCEPTION WHEN duplicate_object THEN null;
            END $$;
        """)

    # users
    op.create_table("users",
        sa.Column("id",              UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("role",            sa.Enum("CUSTOMER","PARTNER","ADMIN", name="user_role", create_type=False), nullable=False),
        sa.Column("name",            sa.String(50),  nullable=False),
        sa.Column("phone",           sa.String(20),  nullable=False, unique=True),
        sa.Column("email",           sa.String(255), unique=True),
        sa.Column("password_hash",   sa.Text),
        sa.Column("business_number", sa.String(20),  unique=True),
        sa.Column("totp_secret",     sa.Text),
        sa.Column("signup_source",   sa.String(50)),
        sa.Column("fcm_token",       sa.Text),
        sa.Column("is_active",       sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_login_at",   sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at",      sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at",      sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # shops
    op.create_table("shops",
        sa.Column("id",           UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("owner_id",     UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name",         sa.String(100), nullable=False),
        sa.Column("address",      sa.Text, nullable=False),
        sa.Column("location",     Geography("POINT", srid=4326), nullable=False),
        sa.Column("team_type",    sa.Enum("DAY","NIGHT","BOTH", name="team_type", create_type=False), nullable=False, server_default="'DAY'"),
        sa.Column("radius_km",    sa.Numeric(4,1), nullable=False, server_default="3.0"),
        sa.Column("rating",       sa.Numeric(3,2), nullable=False, server_default="5.0"),
        sa.Column("review_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active",    sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_available", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("bank_name",    sa.String(50)),
        sa.Column("bank_account", sa.String(30)),
        sa.Column("bank_holder",  sa.String(50)),
        sa.Column("created_at",   sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at",   sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_shops_location_gist", "shops", ["location"], postgresql_using="gist")
    op.create_index("idx_shops_active_available", "shops", ["is_active", "is_available"],
                    postgresql_where=sa.text("is_active = true"))

    # orders
    op.create_table("orders",
        sa.Column("id",               UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("customer_id",      UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id",          UUID(as_uuid=True), sa.ForeignKey("shops.id")),
        sa.Column("service_type",     sa.Enum("DAY","NIGHT", name="service_type", create_type=False), nullable=False),
        sa.Column("wash_category",    sa.Enum("CLOTHES_30L","CLOTHES_50L","BLANKET","SHOES", name="wash_category", create_type=False), nullable=False),
        sa.Column("status",           sa.Enum("PENDING","ACCEPTED","PICKED_UP","WASHING","DRYING","DELIVERING","COMPLETED","CANCELLED", name="order_status", create_type=False), nullable=False, server_default="'PENDING'"),
        sa.Column("pickup_address",   sa.Text, nullable=False),
        sa.Column("pickup_location",  Geography("POINT", srid=4326), nullable=False),
        sa.Column("delivery_address", sa.Text, nullable=False),
        sa.Column("delivery_location",Geography("POINT", srid=4326), nullable=False),
        sa.Column("base_amount",      sa.Integer, nullable=False),
        sa.Column("discount_amount",  sa.Integer, nullable=False, server_default="0"),
        sa.Column("coupon_id",        UUID(as_uuid=True)),
        sa.Column("total_amount",     sa.Integer, nullable=False),
        sa.Column("platform_fee",     sa.Integer, nullable=False, server_default="1000"),
        sa.Column("ordered_at",       sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deadline_at",      sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("accepted_at",      sa.TIMESTAMP(timezone=True)),
        sa.Column("picked_up_at",     sa.TIMESTAMP(timezone=True)),
        sa.Column("completed_at",     sa.TIMESTAMP(timezone=True)),
        sa.Column("cancelled_at",     sa.TIMESTAMP(timezone=True)),
        sa.Column("cancel_reason",    sa.Text),
        sa.Column("version",          sa.Integer, nullable=False, server_default="0"),
        sa.Column("customer_note",    sa.Text),
        sa.Column("created_at",       sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at",       sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_orders_status_deadline", "orders", ["status","deadline_at"],
                    postgresql_where=sa.text("status NOT IN ('COMPLETED','CANCELLED')"))
    op.create_index("idx_orders_customer_ordered", "orders", ["customer_id", sa.text("ordered_at DESC")])
    op.create_index("idx_orders_shop_ordered", "orders", ["shop_id", sa.text("ordered_at DESC")],
                    postgresql_where=sa.text("shop_id IS NOT NULL"))

    # order_status_history
    op.create_table("order_status_history",
        sa.Column("id",         sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("order_id",   UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("old_status", sa.Enum("PENDING","ACCEPTED","PICKED_UP","WASHING","DRYING","DELIVERING","COMPLETED","CANCELLED", name="order_status", create_type=False)),
        sa.Column("new_status", sa.Enum("PENDING","ACCEPTED","PICKED_UP","WASHING","DRYING","DELIVERING","COMPLETED","CANCELLED", name="order_status", create_type=False), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("note",       sa.Text),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # order_photos
    op.create_table("order_photos",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("order_id",    UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("photo_type",  sa.Enum("PICKUP","DELIVERY","ISSUE", name="photo_type", create_type=False), nullable=False),
        sa.Column("s3_key",      sa.Text, nullable=False),
        sa.Column("s3_bucket",   sa.Text, nullable=False, server_default="'sepang-photos'"),
        sa.Column("taken_at",    sa.TIMESTAMP(timezone=True)),
        sa.Column("gps_lat",     sa.Numeric(10,7)),
        sa.Column("gps_lng",     sa.Numeric(10,7)),
        sa.Column("created_at",  sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # settlements
    op.create_table("settlements",
        sa.Column("id",           UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("shop_id",      UUID(as_uuid=True), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end",   sa.Date, nullable=False),
        sa.Column("order_count",  sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_sales",  sa.Integer, nullable=False, server_default="0"),
        sa.Column("platform_fee", sa.Integer, nullable=False, server_default="0"),
        sa.Column("net_payout",   sa.Integer, nullable=False, server_default="0"),
        sa.Column("payout_date",  sa.Date),
        sa.Column("paid_at",      sa.TIMESTAMP(timezone=True)),
        sa.Column("status",       sa.Enum("PENDING","PROCESSING","COMPLETED","FAILED", name="settlement_status", create_type=False), nullable=False, server_default="'PENDING'"),
        sa.Column("transfer_ref", sa.String(100)),
        sa.Column("created_at",   sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at",   sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("shop_id","period_start","period_end"),
    )
    op.create_index("idx_settlements_shop_period", "settlements", ["shop_id", sa.text("period_start DESC")])

    # coupons, user_coupons, point_transactions
    op.create_table("coupons",
        sa.Column("id",              UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code",            sa.String(20), unique=True, nullable=False),
        sa.Column("name",            sa.String(100), nullable=False),
        sa.Column("discount_amount", sa.Integer),
        sa.Column("discount_rate",   sa.Numeric(5,2)),
        sa.Column("min_order_amount",sa.Integer, nullable=False, server_default="0"),
        sa.Column("expires_at",      sa.TIMESTAMP(timezone=True)),
        sa.Column("max_uses",        sa.Integer),
        sa.Column("used_count",      sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active",       sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at",      sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_table("user_coupons",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id",    UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coupon_id",  UUID(as_uuid=True), sa.ForeignKey("coupons.id"), nullable=False),
        sa.Column("used_at",    sa.TIMESTAMP(timezone=True)),
        sa.Column("order_id",   UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("user_id","coupon_id"),
    )
    op.create_table("point_transactions",
        sa.Column("id",         sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id",    UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount",     sa.Integer, nullable=False),
        sa.Column("balance",    sa.Integer, nullable=False),
        sa.Column("reason",     sa.String(100), nullable=False),
        sa.Column("order_id",   UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # reviews
    op.create_table("reviews",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("order_id",    UUID(as_uuid=True), sa.ForeignKey("orders.id"), unique=True, nullable=False),
        sa.Column("customer_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id",     UUID(as_uuid=True), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("rating",      sa.SmallInteger, nullable=False),
        sa.Column("content",     sa.Text),
        sa.Column("is_public",   sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at",  sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # notifications, crm_campaigns
    op.create_table("notifications",
        sa.Column("id",          sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id",     UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id",    UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("type",        sa.Enum("FCM","KAKAO","SMS", name="notification_type", create_type=False), nullable=False),
        sa.Column("title",       sa.String(200), nullable=False),
        sa.Column("body",        sa.Text, nullable=False),
        sa.Column("sent_at",     sa.TIMESTAMP(timezone=True)),
        sa.Column("read_at",     sa.TIMESTAMP(timezone=True)),
        sa.Column("failed_at",   sa.TIMESTAMP(timezone=True)),
        sa.Column("retry_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("created_at",  sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_notifications_unsent", "notifications", ["created_at"],
                    postgresql_where=sa.text("sent_at IS NULL AND failed_at IS NULL"))

    op.create_table("crm_campaigns",
        sa.Column("id",            UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name",          sa.String(200), nullable=False),
        sa.Column("segment",       sa.String(100), nullable=False),
        sa.Column("trigger_rule",  JSONB, nullable=False),
        sa.Column("message_title", sa.String(200), nullable=False),
        sa.Column("message_body",  sa.Text, nullable=False),
        sa.Column("coupon_id",     UUID(as_uuid=True), sa.ForeignKey("coupons.id")),
        sa.Column("status",        sa.Enum("WAITING","SCHEDULED","SENT","FAILED", name="crm_status", create_type=False), nullable=False, server_default="'WAITING'"),
        sa.Column("scheduled_at",  sa.TIMESTAMP(timezone=True)),
        sa.Column("sent_count",    sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at",    sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # otp_verifications, admin_audit_logs
    op.create_table("otp_verifications",
        sa.Column("id",          UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id",     UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("phone",       sa.String(20)),
        sa.Column("code",        sa.String(64), nullable=False),
        sa.Column("purpose",     sa.String(30), nullable=False),
        sa.Column("expires_at",  sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("attempts",    sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("created_at",  sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_otp_expires", "otp_verifications", ["expires_at"],
                    postgresql_where=sa.text("verified_at IS NULL"))

    op.create_table("admin_audit_logs",
        sa.Column("id",          sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("admin_id",    UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ip_address",  sa.String(45), nullable=False),
        sa.Column("user_agent",  sa.Text),
        sa.Column("path",        sa.String(200)),
        sa.Column("action",      sa.String(100)),
        sa.Column("created_at",  sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # DB 함수 및 트리거 (SQL 파일에서 실행)
    op.execute("""
    CREATE OR REPLACE FUNCTION set_order_deadline()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.deadline_at := NEW.ordered_at + INTERVAL '12 hours';
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER trg_order_deadline
        BEFORE INSERT ON orders
        FOR EACH ROW EXECUTE FUNCTION set_order_deadline()
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION accept_order(p_order_id UUID, p_shop_id UUID, p_version INTEGER)
    RETURNS BOOLEAN AS $$
    DECLARE rows_updated INTEGER;
    BEGIN
        UPDATE orders SET status='ACCEPTED', shop_id=p_shop_id, accepted_at=NOW(),
            version=version+1, updated_at=NOW()
        WHERE id=p_order_id AND status='PENDING' AND version=p_version;
        GET DIAGNOSTICS rows_updated = ROW_COUNT;
        RETURN rows_updated > 0;
    END;
    $$ LANGUAGE plpgsql
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION update_shop_rating()
    RETURNS TRIGGER AS $$
    BEGIN
        UPDATE shops SET
            rating=(SELECT AVG(rating) FROM reviews WHERE shop_id=NEW.shop_id AND is_public),
            review_count=(SELECT COUNT(*) FROM reviews WHERE shop_id=NEW.shop_id AND is_public),
            updated_at=NOW()
        WHERE id=NEW.shop_id;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """)
    op.execute("""
    CREATE TRIGGER trg_shop_rating
        AFTER INSERT OR UPDATE ON reviews
        FOR EACH ROW EXECUTE FUNCTION update_shop_rating()
    """)


def downgrade() -> None:
    for tbl in ["admin_audit_logs","otp_verifications","crm_campaigns","notifications",
                "reviews","point_transactions","user_coupons","coupons",
                "settlements","order_photos","order_status_history","orders","shops","users"]:
        op.drop_table(tbl)
    for enum in ["user_role","service_type","team_type","order_status","photo_type",
                 "settlement_status","notification_type","crm_status","wash_category"]:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
