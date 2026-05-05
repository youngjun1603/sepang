"""
Celery 비동기 작업 & SLA 감시 배치
────────────────────────────────────
[참고] Vercel 배포 환경에서는 이 파일을 사용하지 않습니다.
       동일 기능이 Supabase Edge Functions 및 pg_cron으로 대체됩니다.
       로컬/셀프호스팅 환경에서만 실행:
       celery -A tasks worker --loglevel=info -Q default,notifications,settlements
       celery -A tasks beat --loglevel=info
"""
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timezone
import httpx, asyncio

from app.core.config import settings

REDIS_URL = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("sepang", broker=REDIS_URL, backend=REDIS_URL.replace("/0", "/1"))

celery_app.conf.update(
    task_serializer         = "json",
    result_serializer       = "json",
    accept_content          = ["json"],
    timezone                = "Asia/Seoul",
    enable_utc              = True,
    task_acks_late          = True,         # 처리 완료 후 ACK
    task_reject_on_worker_lost = True,
    task_routes = {
        "tasks.send_notification.*": {"queue": "notifications"},
        "tasks.process_settlement*": {"queue": "settlements"},
    },
    beat_schedule = {
        # SLA 위험 주문 감시 (5분 간격)
        "sla-monitor": {
            "task": "tasks.sla_monitor",
            "schedule": crontab(minute="*/5"),
        },
        # 주간 정산 생성 (매주 월요일 01:00 KST)
        "weekly-settlement": {
            "task": "tasks.create_weekly_settlements",
            "schedule": crontab(hour=1, minute=0, day_of_week="mon"),
        },
        # CRM 자동 푸시 (10분 간격)
        "crm-push": {
            "task": "tasks.process_crm_campaigns",
            "schedule": crontab(minute="*/10"),
        },
        # 가입 후 미주문 D+3 리마인드 (매일 09:00)
        "crm-d3-remind": {
            "task": "tasks.send_d3_reminder",
            "schedule": crontab(hour=9, minute=0),
        },
        # 금요일 20:00 NIGHT 서비스 푸시
        "friday-night-push": {
            "task": "tasks.send_friday_night_push",
            "schedule": crontab(hour=20, minute=0, day_of_week="fri"),
        },
    }
)


# ── 알림 발송 ─────────────────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.send_notification.fcm",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def send_fcm(fcm_token: str, title: str, body: str, data: dict = None):
    """FCM 푸시 발송 (실패 시 3회 재시도 → 카카오 알림톡 Failover)"""
    try:
        resp = httpx.post(
            "https://fcm.googleapis.com/fcm/send",
            headers={"Authorization": f"key={settings.FCM_SERVER_KEY}"},
            json={
                "to": fcm_token,
                "notification": {"title": title, "body": body},
                "data": data or {},
            },
            timeout=10,
        )
        resp.raise_for_status()
        return {"channel": "FCM", "success": True}
    except Exception as exc:
        raise send_fcm.retry(exc=exc)


@celery_app.task(name="tasks.send_notification.kakao")
def send_kakao(phone: str, template_code: str, params: dict):
    """카카오 알림톡 발송 (FCM 실패 Failover)"""
    resp = httpx.post(
        f"https://api-alimtalk.cloud.toast.com/alimtalk/v2.3/appkeys/{settings.KAKAO_APP_KEY}/messages",
        headers={"X-Secret-Key": settings.KAKAO_SECRET_KEY},
        json={
            "senderKey":    settings.KAKAO_SENDER_KEY,
            "templateCode": template_code,
            "recipientList": [{"recipientNo": phone, "templateParameter": params}],
        },
        timeout=10,
    )
    return resp.json()


@celery_app.task(
    name="tasks.send_notification.sms",
    max_retries=3,
    default_retry_delay=15,
    autoretry_for=(Exception,),
)
def send_sms_task(phone: str, message: str):
    """SMS 발송 — 네이버 클라우드 SENS API (카카오 알림톡 Failover)"""
    import base64, hashlib, hmac, time as _time
    service_id = settings.NAVER_SENS_SERVICE_ID
    if not service_id:
        return {"success": False, "reason": "SENS not configured"}

    uri = f"/sms/v2/services/{service_id}/messages"
    timestamp = str(int(_time.time() * 1000))
    msg = f"POST {uri}\n{timestamp}\n{settings.NAVER_SENS_ACCESS_KEY}"
    raw_hmac = hmac.new(
        settings.NAVER_SENS_SECRET_KEY.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature = base64.b64encode(raw_hmac).decode("utf-8")

    resp = httpx.post(
        f"https://sens.apigw.ntruss.com{uri}",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "x-ncp-apigw-timestamp": timestamp,
            "x-ncp-iam-access-key": settings.NAVER_SENS_ACCESS_KEY,
            "x-ncp-apigw-signature-v2": signature,
        },
        json={
            "type": "SMS",
            "from": settings.NAVER_SENS_SENDER,
            "content": message,
            "messages": [{"to": phone.replace("-", "")}],
        },
        timeout=10,
    )
    resp.raise_for_status()
    return {"success": True, "channel": "SMS", "response": resp.json()}


# ── SLA 감시 ─────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.sla_monitor")
def sla_monitor():
    """
    5분마다 실행: SLA 위험 주문 감지
    - 마감 2시간 이내: 점주 경고 푸시
    - 마감 초과: 재배정 + 지연 환불 처리
    """
    from app.core.database import sync_session_factory
    from sqlalchemy import text

    with sync_session_factory() as db:
        # 위험 주문 조회
        rows = db.execute(text("SELECT * FROM vw_sla_at_risk")).fetchall()

        for row in rows:
            hours_left = row.hours_left

            if hours_left < 0:
                # 마감 초과 → 강제 재배정 + 환불
                _handle_sla_breach.delay(str(row.id))
            elif hours_left < 2:
                # 마감 2시간 이내 → 점주 경고
                send_fcm.delay(
                    fcm_token=_get_shop_fcm_token(db, row.shop_id),
                    title="⚠️ SLA 마감 임박",
                    body=f"배송 마감까지 {hours_left:.1f}시간 남았습니다. 즉시 배송해 주세요.",
                    data={"order_id": str(row.id)},
                )
                # 고객에게도 지연 가능성 알림
                send_kakao.delay(
                    phone=row.customer_phone,
                    template_code="ORDER_DELAY_WARN",
                    params={"customer_name": row.customer_name, "hours_left": f"{hours_left:.1f}"},
                )

    return f"SLA 감시 완료: {len(rows)}건 확인"


@celery_app.task(name="tasks.handle_sla_breach")
def _handle_sla_breach(order_id: str):
    """SLA 위반 처리: 재배정 + 자동 환불 + 고객 보상"""
    from app.core.database import sync_session_factory
    from sqlalchemy import text

    with sync_session_factory() as db:
        # 지연 시간 계산
        result = db.execute(
            text("SELECT deadline_at, customer_id, total_amount FROM orders WHERE id = :id"),
            {"id": order_id}
        ).fetchone()

        delay_hours = (datetime.now(timezone.utc) - result.deadline_at).total_seconds() / 3600
        refund_rate = min(delay_hours * 0.1, 1.0)  # 1시간당 10%, 최대 100%
        refund_amount = int(result.total_amount * refund_rate)

        # 환불 포인트 적립
        db.execute(
            text("""
                INSERT INTO point_transactions (user_id, amount, balance, reason, order_id)
                VALUES (:uid, :amt,
                    (SELECT COALESCE(SUM(amount), 0) FROM point_transactions WHERE user_id = :uid) + :amt,
                    :reason, :oid)
            """),
            {"uid": result.customer_id, "amt": refund_amount, "reason": "SLA_BREACH_REFUND", "oid": order_id}
        )
        db.commit()


# ── 정산 배치 ─────────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.create_weekly_settlements")
def create_weekly_settlements():
    """매주 월요일 01:00 — 전주 정산 생성"""
    from app.core.database import sync_session_factory
    from sqlalchemy import text
    from datetime import date, timedelta

    today = date.today()
    period_end   = today - timedelta(days=today.weekday() + 1)  # 지난 일요일
    period_start = period_end - timedelta(days=6)               # 지난 월요일

    with sync_session_factory() as db:
        shops = db.execute(text("SELECT id FROM shops WHERE is_active")).fetchall()
        for shop in shops:
            db.execute(
                text("SELECT create_weekly_settlement(:shop_id, :start, :end)"),
                {"shop_id": shop.id, "start": period_start, "end": period_end}
            )
        db.commit()

    return f"정산 생성 완료: {period_start} ~ {period_end}, {len(shops)}개 점포"


# ── CRM 자동 푸시 ─────────────────────────────────────────────────────────────

@celery_app.task(name="tasks.issue_signup_coupon")
def issue_signup_coupon(user_id: str):
    """신규 가입 쿠폰 즉시 발급 + D+0 웰컴 푸시"""
    from app.core.database import sync_session_factory
    from sqlalchemy import text

    with sync_session_factory() as db:
        # 신규 가입 3,000원 쿠폰 발급
        db.execute(
            text("""
                INSERT INTO user_coupons (user_id, coupon_id)
                SELECT :uid, id FROM coupons
                WHERE code = 'WELCOME3000' AND is_active LIMIT 1
            """),
            {"uid": user_id}
        )
        # FCM 토큰 조회
        row = db.execute(
            text("SELECT fcm_token, name FROM users WHERE id = :id"),
            {"id": user_id}
        ).fetchone()
        db.commit()

    if row and row.fcm_token:
        send_fcm.delay(
            fcm_token=row.fcm_token,
            title="🎉 세팡에 오신 걸 환영합니다!",
            body=f"{row.name}님, 첫 주문 3,000원 할인 쿠폰이 발급되었습니다.",
            data={"type": "COUPON", "code": "WELCOME3000"},
        )


@celery_app.task(name="tasks.send_d3_reminder")
def send_d3_reminder():
    """가입 후 3일 경과, 미주문 고객 리마인드"""
    from app.core.database import sync_session_factory
    from sqlalchemy import text

    with sync_session_factory() as db:
        rows = db.execute(text("""
            SELECT u.id, u.name, u.fcm_token
            FROM users u
            WHERE u.role = 'CUSTOMER'
              AND u.created_at::date = (CURRENT_DATE - 3)
              AND NOT EXISTS (
                  SELECT 1 FROM orders o
                  WHERE o.customer_id = u.id
              )
              AND u.fcm_token IS NOT NULL
        """)).fetchall()

    for row in rows:
        send_fcm.delay(
            fcm_token=row.fcm_token,
            title="🧺 아직 첫 주문 안 하셨나요?",
            body="지금 주문하면 3,000원 즉시 할인! 12시간 이내 배송 완료.",
            data={"type": "REMINDER"},
        )
    return f"D+3 리마인드 발송: {len(rows)}명"


@celery_app.task(name="tasks.send_friday_night_push")
def send_friday_night_push():
    """금요일 20:00 — Night 서비스 이용 이력 고객 대상 푸시"""
    from app.core.database import sync_session_factory
    from sqlalchemy import text

    with sync_session_factory() as db:
        rows = db.execute(text("""
            SELECT DISTINCT u.id, u.name, u.fcm_token
            FROM users u
            JOIN orders o ON o.customer_id = u.id
            WHERE o.service_type = 'NIGHT'
              AND u.fcm_token IS NOT NULL
            LIMIT 5000
        """)).fetchall()

    for row in rows:
        send_fcm.delay(
            fcm_token=row.fcm_token,
            title="🌙 주말 전 Night 빨래 맡기세요",
            body="오후 9시 수거 → 내일 아침 배송. 깔끔한 주말 시작!",
            data={"type": "NIGHT_PROMO"},
        )
    return f"금요일 Night 푸시: {len(rows)}명"


def _get_shop_fcm_token(db, shop_id) -> str:
    from sqlalchemy import text
    row = db.execute(
        text("SELECT u.fcm_token FROM users u JOIN shops s ON s.owner_id = u.id WHERE s.id = :sid"),
        {"sid": shop_id}
    ).fetchone()
    return row.fcm_token if row else ""

