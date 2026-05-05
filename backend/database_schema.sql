-- ============================================================
-- 세팡 (SEPANG) Production Database Schema
-- PostgreSQL 16 + PostGIS 3.4
-- ============================================================

-- 확장 설치
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- 텍스트 검색

-- ────────────────────────────────────────────────────────────
--  ENUM TYPES
-- ────────────────────────────────────────────────────────────
CREATE TYPE user_role        AS ENUM ('CUSTOMER', 'PARTNER', 'ADMIN');
CREATE TYPE service_type     AS ENUM ('DAY', 'NIGHT');
CREATE TYPE team_type        AS ENUM ('DAY', 'NIGHT', 'BOTH');
CREATE TYPE order_status     AS ENUM (
    'PENDING',      -- 점주 배정 대기
    'ACCEPTED',     -- 점주 수락
    'PICKED_UP',    -- 수거 완료
    'WASHING',      -- 세탁 중
    'DRYING',       -- 건조 중
    'DELIVERING',   -- 배송 중
    'COMPLETED',    -- 배송 완료
    'CANCELLED'     -- 취소
);
CREATE TYPE photo_type       AS ENUM ('PICKUP', 'DELIVERY', 'ISSUE');
CREATE TYPE settlement_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
CREATE TYPE notification_type AS ENUM ('FCM', 'KAKAO', 'SMS');
CREATE TYPE crm_status       AS ENUM ('WAITING', 'SCHEDULED', 'SENT', 'FAILED');
CREATE TYPE wash_category    AS ENUM ('CLOTHES_30L', 'CLOTHES_50L', 'BLANKET', 'SHOES');


-- ────────────────────────────────────────────────────────────
--  USERS
-- ────────────────────────────────────────────────────────────
CREATE TABLE users (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    role                user_role       NOT NULL,
    name                VARCHAR(50)     NOT NULL,
    phone               VARCHAR(20)     UNIQUE NOT NULL,
    email               VARCHAR(255)    UNIQUE,
    password_hash       TEXT,                               -- 점주/관리자용
    business_number     VARCHAR(20)     UNIQUE,             -- 점주 사업자번호
    signup_source       VARCHAR(50),                        -- 유입 채널 (CRM)
    fcm_token           TEXT,                               -- Firebase 푸시 토큰
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- OTP 인증 (고객 휴대폰, 관리자 TOTP)
CREATE TABLE otp_verifications (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID        REFERENCES users(id) ON DELETE CASCADE,
    phone           VARCHAR(20),                            -- 미가입 고객 인증용
    code            VARCHAR(10) NOT NULL,
    purpose         VARCHAR(30) NOT NULL,                   -- 'LOGIN', 'SIGNUP', 'ADMIN_2FA'
    expires_at      TIMESTAMPTZ NOT NULL,
    verified_at     TIMESTAMPTZ,
    attempts        SMALLINT    NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 관리자 접근 감사 로그
CREATE TABLE admin_audit_logs (
    id          BIGSERIAL   PRIMARY KEY,
    admin_id    UUID        NOT NULL REFERENCES users(id),
    ip_address  INET        NOT NULL,
    user_agent  TEXT,
    path        VARCHAR(200),
    action      VARCHAR(100),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
--  SHOPS (파트너 점포)
-- ────────────────────────────────────────────────────────────
CREATE TABLE shops (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID        NOT NULL REFERENCES users(id),
    name            VARCHAR(100) NOT NULL,
    address         TEXT        NOT NULL,
    -- PostGIS 지리 좌표 (WGS84 SRID=4326)
    location        GEOGRAPHY(POINT, 4326) NOT NULL,
    team_type       team_type   NOT NULL DEFAULT 'DAY',
    radius_km       NUMERIC(4,1) NOT NULL DEFAULT 3.0,      -- 담당 반경
    rating          NUMERIC(3,2) NOT NULL DEFAULT 5.0 CHECK (rating BETWEEN 1 AND 5),
    review_count    INTEGER     NOT NULL DEFAULT 0,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    is_available    BOOLEAN     NOT NULL DEFAULT FALSE,      -- 현재 수락 가능 여부
    bank_name       VARCHAR(50),
    bank_account    VARCHAR(30),
    bank_holder     VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
--  ORDERS
-- ────────────────────────────────────────────────────────────
CREATE TABLE orders (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id         UUID            NOT NULL REFERENCES users(id),
    shop_id             UUID            REFERENCES shops(id),  -- 배정 전 NULL

    service_type        service_type    NOT NULL,
    wash_category       wash_category   NOT NULL,
    status              order_status    NOT NULL DEFAULT 'PENDING',

    -- 주소 & 좌표
    pickup_address      TEXT            NOT NULL,
    pickup_location     GEOGRAPHY(POINT, 4326) NOT NULL,
    delivery_address    TEXT            NOT NULL,
    delivery_location   GEOGRAPHY(POINT, 4326) NOT NULL,

    -- 금액
    base_amount         INTEGER         NOT NULL,           -- 서비스 금액
    discount_amount     INTEGER         NOT NULL DEFAULT 0,
    coupon_id           UUID,
    total_amount        INTEGER         NOT NULL,           -- 실결제
    platform_fee        INTEGER         NOT NULL DEFAULT 1000,

    -- SLA
    ordered_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deadline_at         TIMESTAMPTZ     NOT NULL,           -- ordered_at + 12h
    accepted_at         TIMESTAMPTZ,
    picked_up_at        TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    cancel_reason       TEXT,

    -- 낙관적 잠금 (동시 수락 방지)
    version             INTEGER         NOT NULL DEFAULT 0,

    -- 특이사항
    customer_note       TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- deadline_at 자동 계산 트리거
CREATE OR REPLACE FUNCTION set_order_deadline()
RETURNS TRIGGER AS $$
BEGIN
    -- DAY: 주문 후 +12시간, NIGHT: 주문 후 +12시간
    NEW.deadline_at := NEW.ordered_at + INTERVAL '12 hours';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_deadline
    BEFORE INSERT ON orders
    FOR EACH ROW EXECUTE FUNCTION set_order_deadline();

-- 낙관적 잠금 수락 함수 (동시 다중 점주 수락 방지)
CREATE OR REPLACE FUNCTION accept_order(
    p_order_id  UUID,
    p_shop_id   UUID,
    p_version   INTEGER
) RETURNS BOOLEAN AS $$
DECLARE
    rows_updated INTEGER;
BEGIN
    UPDATE orders
    SET status      = 'ACCEPTED',
        shop_id     = p_shop_id,
        accepted_at = NOW(),
        version     = version + 1,
        updated_at  = NOW()
    WHERE id        = p_order_id
      AND status    = 'PENDING'
      AND version   = p_version;

    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    RETURN rows_updated > 0;
END;
$$ LANGUAGE plpgsql;


-- ────────────────────────────────────────────────────────────
--  ORDER STATUS HISTORY
-- ────────────────────────────────────────────────────────────
CREATE TABLE order_status_history (
    id          BIGSERIAL       PRIMARY KEY,
    order_id    UUID            NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    old_status  order_status,
    new_status  order_status    NOT NULL,
    changed_by  UUID            REFERENCES users(id),
    note        TEXT,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 상태 변경 자동 기록 트리거
CREATE OR REPLACE FUNCTION log_order_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO order_status_history(order_id, old_status, new_status, changed_by)
        VALUES (NEW.id, OLD.status, NEW.status, NULL);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_order_status_history
    AFTER UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION log_order_status_change();


-- ────────────────────────────────────────────────────────────
--  ORDER PHOTOS (S3 증빙 사진)
-- ────────────────────────────────────────────────────────────
CREATE TABLE order_photos (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id        UUID        NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    uploader_id     UUID        NOT NULL REFERENCES users(id),
    photo_type      photo_type  NOT NULL,
    -- S3 키 형식: photos/{order_id}/{type}/{uuid}.jpg
    s3_key          TEXT        NOT NULL,
    s3_bucket       TEXT        NOT NULL DEFAULT 'sepang-photos',
    -- 메타데이터 (EXIF GPS, 타임스탬프)
    taken_at        TIMESTAMPTZ,
    gps_lat         NUMERIC(10,7),
    gps_lng         NUMERIC(10,7),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
--  SETTLEMENTS (정산)
-- ────────────────────────────────────────────────────────────
CREATE TABLE settlements (
    id              UUID                PRIMARY KEY DEFAULT uuid_generate_v4(),
    shop_id         UUID                NOT NULL REFERENCES shops(id),
    period_start    DATE                NOT NULL,
    period_end      DATE                NOT NULL,
    order_count     INTEGER             NOT NULL DEFAULT 0,
    total_sales     INTEGER             NOT NULL DEFAULT 0,    -- 총 매출
    platform_fee    INTEGER             NOT NULL DEFAULT 0,    -- 수수료 합계
    net_payout      INTEGER             NOT NULL DEFAULT 0,    -- 실 지급액
    payout_date     DATE,                                      -- 예정 지급일
    paid_at         TIMESTAMPTZ,
    status          settlement_status   NOT NULL DEFAULT 'PENDING',
    transfer_ref    VARCHAR(100),                              -- 이체 참조번호
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    UNIQUE (shop_id, period_start, period_end)
);

-- 주간 정산 자동 집계 함수
CREATE OR REPLACE FUNCTION create_weekly_settlement(
    p_shop_id       UUID,
    p_period_start  DATE,
    p_period_end    DATE
) RETURNS UUID AS $$
DECLARE
    v_count     INTEGER;
    v_sales     INTEGER;
    v_fee       INTEGER;
    v_id        UUID;
BEGIN
    SELECT
        COUNT(*),
        COALESCE(SUM(total_amount), 0),
        COALESCE(SUM(platform_fee), 0)
    INTO v_count, v_sales, v_fee
    FROM orders
    WHERE shop_id       = p_shop_id
      AND status        = 'COMPLETED'
      AND completed_at  >= p_period_start::TIMESTAMPTZ
      AND completed_at  <  (p_period_end + INTERVAL '1 day')::TIMESTAMPTZ;

    INSERT INTO settlements (
        shop_id, period_start, period_end,
        order_count, total_sales, platform_fee, net_payout,
        payout_date, status
    ) VALUES (
        p_shop_id, p_period_start, p_period_end,
        v_count, v_sales, v_fee, v_sales - v_fee,
        p_period_end + INTERVAL '5 days',
        'PENDING'
    )
    ON CONFLICT (shop_id, period_start, period_end) DO UPDATE
    SET order_count = EXCLUDED.order_count,
        total_sales = EXCLUDED.total_sales,
        platform_fee= EXCLUDED.platform_fee,
        net_payout  = EXCLUDED.net_payout,
        updated_at  = NOW()
    RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;


-- ────────────────────────────────────────────────────────────
--  COUPONS & POINTS
-- ────────────────────────────────────────────────────────────
CREATE TABLE coupons (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    code            VARCHAR(20) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    discount_amount INTEGER,                                -- 정액 할인
    discount_rate   NUMERIC(5,2),                           -- 퍼센트 할인 (0~100)
    min_order_amount INTEGER     NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ,
    max_uses        INTEGER,
    used_count      INTEGER     NOT NULL DEFAULT 0,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE user_coupons (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coupon_id   UUID        NOT NULL REFERENCES coupons(id),
    used_at     TIMESTAMPTZ,
    order_id    UUID        REFERENCES orders(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, coupon_id)
);

CREATE TABLE point_transactions (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     UUID        NOT NULL REFERENCES users(id),
    amount      INTEGER     NOT NULL,                       -- 양수: 적립, 음수: 사용
    balance     INTEGER     NOT NULL,
    reason      VARCHAR(100) NOT NULL,                      -- 'REVIEW', 'ORDER_CANCEL', etc.
    order_id    UUID        REFERENCES orders(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
--  REVIEWS
-- ────────────────────────────────────────────────────────────
CREATE TABLE reviews (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id    UUID        NOT NULL UNIQUE REFERENCES orders(id),
    customer_id UUID        NOT NULL REFERENCES users(id),
    shop_id     UUID        NOT NULL REFERENCES shops(id),
    rating      SMALLINT    NOT NULL CHECK (rating BETWEEN 1 AND 5),
    content     TEXT,
    is_public   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 리뷰 작성 후 점포 평점 갱신 트리거
CREATE OR REPLACE FUNCTION update_shop_rating()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE shops
    SET rating       = (SELECT AVG(rating) FROM reviews WHERE shop_id = NEW.shop_id AND is_public),
        review_count = (SELECT COUNT(*)    FROM reviews WHERE shop_id = NEW.shop_id AND is_public),
        updated_at   = NOW()
    WHERE id = NEW.shop_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_shop_rating
    AFTER INSERT OR UPDATE ON reviews
    FOR EACH ROW EXECUTE FUNCTION update_shop_rating();


-- ────────────────────────────────────────────────────────────
--  NOTIFICATIONS
-- ────────────────────────────────────────────────────────────
CREATE TABLE notifications (
    id              BIGSERIAL               PRIMARY KEY,
    user_id         UUID                    NOT NULL REFERENCES users(id),
    order_id        UUID                    REFERENCES orders(id),
    type            notification_type       NOT NULL,
    title           VARCHAR(200)            NOT NULL,
    body            TEXT                    NOT NULL,
    sent_at         TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,
    failed_at       TIMESTAMPTZ,
    retry_count     SMALLINT                NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
--  CRM 마케팅 푸시 시나리오
-- ────────────────────────────────────────────────────────────
CREATE TABLE crm_campaigns (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    segment         VARCHAR(100) NOT NULL,                  -- 'NEW_USER_D3', 'VIP_5TH', etc.
    trigger_rule    JSONB       NOT NULL,                    -- 발송 조건
    message_title   VARCHAR(200) NOT NULL,
    message_body    TEXT        NOT NULL,
    coupon_id       UUID        REFERENCES coupons(id),
    status          crm_status  NOT NULL DEFAULT 'WAITING',
    scheduled_at    TIMESTAMPTZ,
    sent_count      INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
--  INDEXES
-- ────────────────────────────────────────────────────────────

-- 주문 상태 + 마감시간 (SLA 모니터링)
CREATE INDEX idx_orders_status_deadline
    ON orders(status, deadline_at)
    WHERE status NOT IN ('COMPLETED', 'CANCELLED');

-- 고객별 주문 내역 (내 주문 화면)
CREATE INDEX idx_orders_customer_ordered
    ON orders(customer_id, ordered_at DESC);

-- 점포별 주문 (점주 앱)
CREATE INDEX idx_orders_shop_ordered
    ON orders(shop_id, ordered_at DESC)
    WHERE shop_id IS NOT NULL;

-- 반경 내 점포 검색 (PostGIS GIST 인덱스)
CREATE INDEX idx_shops_location_gist
    ON shops USING GIST(location);

-- 점포 가용 여부
CREATE INDEX idx_shops_active_available
    ON shops(is_active, is_available)
    WHERE is_active = TRUE;

-- 정산 기간별 조회
CREATE INDEX idx_settlements_shop_period
    ON settlements(shop_id, period_start DESC);

-- 알림 미전송 큐
CREATE INDEX idx_notifications_unsent
    ON notifications(created_at)
    WHERE sent_at IS NULL AND failed_at IS NULL;

-- OTP 유효기간
CREATE INDEX idx_otp_expires
    ON otp_verifications(expires_at)
    WHERE verified_at IS NULL;


-- ────────────────────────────────────────────────────────────
--  USEFUL VIEWS
-- ────────────────────────────────────────────────────────────

-- SLA 위반 위험 주문 (마감 2시간 이내, 미완료)
CREATE OR REPLACE VIEW vw_sla_at_risk AS
SELECT
    o.id,
    o.status,
    o.deadline_at,
    EXTRACT(EPOCH FROM (o.deadline_at - NOW())) / 3600 AS hours_left,
    o.shop_id,
    s.name AS shop_name,
    o.customer_id,
    u.name AS customer_name,
    u.phone AS customer_phone
FROM orders o
JOIN users u ON u.id = o.customer_id
LEFT JOIN shops s ON s.id = o.shop_id
WHERE o.status NOT IN ('COMPLETED', 'CANCELLED')
  AND o.deadline_at < NOW() + INTERVAL '2 hours';

-- 점포 반경 내 대기 주문 조회 함수
CREATE OR REPLACE FUNCTION get_nearby_orders(
    p_shop_id   UUID,
    p_limit     INTEGER DEFAULT 20
)
RETURNS TABLE (
    order_id        UUID,
    wash_category   wash_category,
    service_type    service_type,
    pickup_address  TEXT,
    distance_m      FLOAT,
    deadline_at     TIMESTAMPTZ,
    total_amount    INTEGER
) AS $$
    SELECT
        o.id,
        o.wash_category,
        o.service_type,
        o.pickup_address,
        ST_Distance(o.pickup_location, sh.location) AS distance_m,
        o.deadline_at,
        o.total_amount
    FROM orders o
    JOIN shops sh ON sh.id = p_shop_id
    WHERE o.status = 'PENDING'
      AND ST_DWithin(o.pickup_location, sh.location, sh.radius_km * 1000)
    ORDER BY o.deadline_at ASC, distance_m ASC
    LIMIT p_limit;
$$ LANGUAGE sql STABLE;

-- 유입 채널별 전환율 (분석)
CREATE OR REPLACE VIEW vw_funnel_conversion AS
SELECT
    u.signup_source,
    COUNT(DISTINCT u.id)                                AS signups,
    COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN u.id END) AS ordered_users,
    ROUND(
        COUNT(DISTINCT CASE WHEN o.id IS NOT NULL THEN u.id END)::NUMERIC
        / NULLIF(COUNT(DISTINCT u.id), 0) * 100, 1
    ) AS conversion_rate
FROM users u
LEFT JOIN orders o ON o.customer_id = u.id
WHERE u.role = 'CUSTOMER'
GROUP BY u.signup_source;

