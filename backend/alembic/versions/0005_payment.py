"""add payment system

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # payment_status ENUM
    op.execute("CREATE TYPE payment_status AS ENUM ('PENDING', 'PAID', 'FAILED', 'CANCELLED', 'REFUNDED')")
    op.execute("CREATE TYPE payment_method AS ENUM ('CARD', 'VIRTUAL_ACCOUNT', 'TRANSFER', 'MOBILE', 'GIFT_CERTIFICATE', 'EASY_PAY')")

    # orders 테이블에 결제 컬럼 추가 (생성한 ENUM 타입 직접 참조)
    op.execute("ALTER TABLE orders ADD COLUMN payment_status payment_status NOT NULL DEFAULT 'PENDING'")
    op.execute("ALTER TABLE orders ADD COLUMN payment_key TEXT")
    op.execute("ALTER TABLE orders ADD COLUMN payment_method payment_method")
    op.execute("ALTER TABLE orders ADD COLUMN paid_at TIMESTAMPTZ")

    # payment_transactions 테이블
    op.create_table(
        "payment_transactions",
        sa.Column("id",             sa.Text(),    primary_key=True),   # Toss paymentKey
        sa.Column("order_id",       sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("amount",         sa.Integer(), nullable=False),
        sa.Column("status",         sa.Text(),    nullable=False),      # payment_status
        sa.Column("method",         sa.Text(),    nullable=True),       # payment_method
        sa.Column("toss_response",  sa.Text(),    nullable=True),       # JSON 원문 보관
        sa.Column("cancel_reason",  sa.Text(),    nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at",     sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_payment_transactions_order_id", "payment_transactions", ["order_id"])


def downgrade():
    op.drop_table("payment_transactions")
    op.drop_column("orders", "paid_at")
    op.drop_column("orders", "payment_method")
    op.drop_column("orders", "payment_key")
    op.drop_column("orders", "payment_status")
    op.execute("DROP TYPE IF EXISTS payment_method")
    op.execute("DROP TYPE IF EXISTS payment_status")
