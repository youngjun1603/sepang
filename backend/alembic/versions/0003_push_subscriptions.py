"""Web Push 구독 테이블 + reviews 컬럼 수정

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # push_subscriptions 테이블 추가 (Web Push VAPID)
    op.create_table(
        "push_subscriptions",
        sa.Column("id",         UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id",    UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint",   sa.Text, nullable=False, unique=True),
        sa.Column("p256dh_key", sa.Text, nullable=False),
        sa.Column("auth_key",   sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_push_subscriptions_user", "push_subscriptions", ["user_id"])

    # reviews.content → comment (api 통일)
    op.alter_column("reviews", "content", new_column_name="comment")


def downgrade() -> None:
    op.alter_column("reviews", "comment", new_column_name="content")
    op.drop_table("push_subscriptions")
