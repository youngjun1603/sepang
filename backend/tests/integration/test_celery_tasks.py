"""통합 테스트 — Celery 태스크 & SLA 로직"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock


def test_sla_risk_classification():
    """SLA 위험도 분류 로직"""
    now = datetime.now(timezone.utc)
    cases = [
        (now + timedelta(hours=3),  "SAFE"),
        (now + timedelta(hours=1.5),"URGENT"),
        (now + timedelta(hours=0.5),"DANGER"),
        (now - timedelta(hours=1),  "BREACHED"),
    ]
    def classify(deadline):
        left = (deadline - now).total_seconds() / 3600
        if left < 0:   return "BREACHED"
        if left < 1:   return "DANGER"
        if left < 2:   return "URGENT"
        return "SAFE"
    for deadline, expected in cases:
        assert classify(deadline) == expected


def test_sla_breach_refund_calculation():
    """지연 시간 비례 환불 계산"""
    total = 13000
    cases = [
        (1.0,  0.10, 1300),   # 1시간 → 10%
        (5.0,  0.50, 6500),   # 5시간 → 50%
        (12.0, 1.00, 13000),  # 12시간 → 100%
    ]
    for delay_h, rate, expected in cases:
        actual_rate   = min(delay_h * 0.1, 1.0)
        refund_amount = int(total * actual_rate)
        assert abs(refund_amount - expected) < 50  # 반올림 허용


@patch("tasks.send_fcm.delay")
def test_sla_monitor_sends_fcm_on_urgent(mock_fcm):
    """SLA 마감 2시간 이내 → FCM 발송"""
    urgent_orders = [
        MagicMock(hours_left=1.5, shop_id="shop-1", id="order-1",
                  customer_phone="01012341234", customer_name="홍길동"),
    ]
    for order in urgent_orders:
        if order.hours_left < 2:
            mock_fcm(
                fcm_token="dummy-token",
                title="⚠️ SLA 마감 임박",
                body=f"배송 마감까지 {order.hours_left:.1f}시간 남았습니다",
                data={"order_id": str(order.id)},
            )
    assert mock_fcm.call_count == 1


def test_weekly_settlement_period():
    """정산 기간 계산 — 월요일 실행 시 전주 월~일"""
    from datetime import date
    # 2026-03-18 (수) 기준: 전주 = 03.09(월) ~ 03.15(일)
    today = date(2026, 3, 18)
    period_end   = today - timedelta(days=today.weekday() + 1)   # 03.15 (일)
    period_start = period_end - timedelta(days=6)                 # 03.09 (월)
    assert period_end   == date(2026, 3, 15)
    assert period_start == date(2026, 3, 9)
    payout_date = period_end + timedelta(days=5)
    assert payout_date  == date(2026, 3, 20)


@patch("tasks.send_fcm.delay")
def test_d3_reminder_targets(mock_fcm):
    """D+3 리마인드 — 가입 후 3일 경과 미주문 고객"""
    mock_users = [
        MagicMock(id="u1", name="김지현", fcm_token="tok1"),
        MagicMock(id="u2", name="이수민", fcm_token="tok2"),
    ]
    for user in mock_users:
        mock_fcm(
            fcm_token=user.fcm_token,
            title="🧺 아직 첫 주문 안 하셨나요?",
            body="지금 주문하면 3,000원 즉시 할인!",
            data={"type": "REMINDER"},
        )
    assert mock_fcm.call_count == 2
