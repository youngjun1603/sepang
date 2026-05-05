"""Seed data — 초기 데이터 (쿠폰, 관리자 계정)

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
import bcrypt, pyotp, uuid

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 웰컴 쿠폰
    op.execute("""
        INSERT INTO coupons (id, code, name, discount_amount, min_order_amount, is_active)
        VALUES
            (uuid_generate_v4(), 'WELCOME3000', '신규 가입 할인', 3000, 10000, true),
            (uuid_generate_v4(), 'REVIEW100',   '리뷰 작성 보상', NULL,  0,     true)
    """)

    # 관리자 계정 (비밀번호: Admin@Sepang2026!)
    pw_hash = bcrypt.hashpw(b"Admin@Sepang2026!", bcrypt.gensalt()).decode()
    totp_secret = pyotp.random_base32()
    admin_id = str(uuid.uuid4())

    op.execute(f"""
        INSERT INTO users (id, role, name, phone, email, password_hash, totp_secret, is_active)
        VALUES (
            '{admin_id}', 'ADMIN', '세팡 관리자', '01000000000',
            'admin@sepang.kr', '{pw_hash}', '{totp_secret}', true
        )
    """)

    # TOTP URI를 마이그레이션 로그에 출력 (최초 설정용)
    totp = pyotp.TOTP(totp_secret)
    uri = totp.provisioning_uri(name="admin@sepang.kr", issuer_name="Sepang Admin")
    print(f"\n⚠️  관리자 TOTP 설정 URI (Google Authenticator에 등록):\n{uri}\n")


def downgrade() -> None:
    op.execute("DELETE FROM users WHERE email = 'admin@sepang.kr'")
    op.execute("DELETE FROM coupons WHERE code IN ('WELCOME3000','REVIEW100')")
