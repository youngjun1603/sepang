"""단위 테스트 — 주문 비즈니스 로직"""
import pytest
from datetime import datetime, timezone, timedelta


# ── 가격표 테스트 ─────────────────────────────────────────────────────────────

PRICE_TABLE = {
    "CLOTHES_30L": 13000,
    "CLOTHES_50L": 18000,
    "BLANKET":     16000,
    "SHOES":       10000,
}

@pytest.mark.parametrize("category,expected", [
    ("CLOTHES_30L", 13000),
    ("CLOTHES_50L", 18000),
    ("BLANKET",     16000),
    ("SHOES",       10000),
])
def test_price_table(category, expected):
    assert PRICE_TABLE[category] == expected


# ── SLA deadline 계산 ─────────────────────────────────────────────────────────

def test_deadline_is_12h_after_order():
    ordered_at = datetime(2026, 3, 18, 9, 0, 0, tzinfo=timezone.utc)
    deadline   = ordered_at + timedelta(hours=12)
    assert deadline == datetime(2026, 3, 18, 21, 0, 0, tzinfo=timezone.utc)


def test_sla_urgency_thresholds():
    now = datetime.now(timezone.utc)
    # 위험: 마감 1시간 이내
    danger_deadline  = now + timedelta(hours=0.5)
    urgent_deadline  = now + timedelta(hours=1.5)
    safe_deadline    = now + timedelta(hours=5)

    def classify(deadline):
        left = (deadline - now).total_seconds() / 3600
        if left < 1:  return "DANGER"
        if left < 2:  return "URGENT"
        return "SAFE"

    assert classify(danger_deadline)  == "DANGER"
    assert classify(urgent_deadline)  == "URGENT"
    assert classify(safe_deadline)    == "SAFE"


# ── 상태 전이 검증 ────────────────────────────────────────────────────────────

PARTNER_TRANSITIONS = {
    "PENDING":    ["ACCEPTED"],
    "ACCEPTED":   ["PICKED_UP"],
    "PICKED_UP":  ["WASHING"],
    "WASHING":    ["DRYING"],
    "DRYING":     ["DELIVERING"],
    "DELIVERING": ["COMPLETED"],
}

@pytest.mark.parametrize("from_status,to_status,expected", [
    ("PENDING",    "ACCEPTED",   True),
    ("ACCEPTED",   "PICKED_UP",  True),
    ("PICKED_UP",  "WASHING",    True),
    ("WASHING",    "DRYING",     True),
    ("DRYING",     "DELIVERING", True),
    ("DELIVERING", "COMPLETED",  True),
    # 역방향 불가
    ("WASHING",    "ACCEPTED",   False),
    ("COMPLETED",  "DELIVERING", False),
    # 건너뜀 불가
    ("PENDING",    "WASHING",    False),
    ("ACCEPTED",   "COMPLETED",  False),
])
def test_status_transitions(from_status, to_status, expected):
    allowed = PARTNER_TRANSITIONS.get(from_status, [])
    assert (to_status in allowed) == expected


# ── 쿠폰 할인 계산 ───────────────────────────────────────────────────────────

def apply_discount(base: int, discount_amount=None, discount_rate=None) -> int:
    if discount_amount: return discount_amount
    if discount_rate:   return int(base * discount_rate / 100)
    return 0

@pytest.mark.parametrize("base,discount_amount,discount_rate,expected", [
    (13000, 3000, None, 3000),   # 정액 할인
    (13000, None, 10,  1300),    # 10% 할인
    (13000, None, None,   0),    # 쿠폰 없음
    (13000, 3000, 10,  3000),    # 정액 우선
])
def test_coupon_discount(base, discount_amount, discount_rate, expected):
    result = apply_discount(base, discount_amount, discount_rate)
    assert result == expected


# ── 정산 계산 ─────────────────────────────────────────────────────────────────

def test_settlement_calculation():
    orders = [
        {"total_amount": 13000, "platform_fee": 1000},
        {"total_amount": 16000, "platform_fee": 1000},
        {"total_amount": 13000, "platform_fee": 1000},
    ]
    total_sales  = sum(o["total_amount"] for o in orders)
    platform_fee = sum(o["platform_fee"] for o in orders)
    net_payout   = total_sales - platform_fee

    assert total_sales  == 42000
    assert platform_fee == 3000
    assert net_payout   == 39000


def test_settlement_payout_date():
    """정산일은 period_end + 5일"""
    from datetime import date, timedelta
    period_end  = date(2026, 3, 8)   # 일요일
    payout_date = period_end + timedelta(days=5)
    assert payout_date == date(2026, 3, 13)  # 목요일


# ── 점포 반경 필터 (간단 거리 계산) ──────────────────────────────────────────

import math

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def test_haversine_within_radius():
    # 강남역 → 역삼역 (~0.9km)
    shop = (37.4979, 127.0276)
    pickup_near = (37.5007, 127.0368)  # ~0.9km
    pickup_far  = (37.5665, 126.9780)  # ~10km
    assert haversine_km(*shop, *pickup_near) < 3.0
    assert haversine_km(*shop, *pickup_far)  > 3.0


# ── OTP 만료 로직 ─────────────────────────────────────────────────────────────

def test_otp_expiry():
    from datetime import datetime, timezone, timedelta
    issued_at  = datetime(2026, 3, 18, 10, 0, 0, tzinfo=timezone.utc)
    expires_at = issued_at + timedelta(minutes=3)
    now_valid  = issued_at + timedelta(minutes=2)
    now_expired= issued_at + timedelta(minutes=4)

    assert now_valid   < expires_at  # 유효
    assert now_expired > expires_at  # 만료
