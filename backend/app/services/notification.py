"""알림 서비스 — FCM + Web Push + 네이버 SENS SMS"""
import asyncio
import base64
import hashlib
import hmac
import json
import time
from typing import Optional

import httpx
from app.core.config import settings


async def send_nearby_partner_notifications(
    order_id: str,
    pickup_lat: float,
    pickup_lng: float,
    wash_category: str,
    total_amount: int,
):
    """주문 생성 시 반경 3km 내 점주에게 FCM 푸시"""
    from app.core.database import sync_session_factory
    from sqlalchemy import text

    with sync_session_factory() as db:
        shops = db.execute(text("""
            SELECT u.fcm_token
            FROM shops s
            JOIN users u ON u.id = s.owner_id
            WHERE s.is_active AND s.is_available
              AND ST_DWithin(
                s.location,
                ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                s.radius_km * 1000
              )
              AND u.fcm_token IS NOT NULL
        """), {"lat": pickup_lat, "lng": pickup_lng}).fetchall()

    tasks = [
        _send_fcm(
            fcm_token=shop.fcm_token,
            title="📦 새 주문이 들어왔습니다",
            body=f"{wash_category} · {total_amount:,}원",
            data={"order_id": order_id, "type": "NEW_ORDER"},
        )
        for shop in shops
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _send_fcm(fcm_token: str, title: str, body: str, data: dict = None):
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            "https://fcm.googleapis.com/fcm/send",
            headers={"Authorization": f"key={settings.FCM_SERVER_KEY}"},
            json={
                "to": fcm_token,
                "notification": {"title": title, "body": body},
                "data": data or {},
            },
        )


async def send_sms(phone: str, message: str) -> dict:
    """
    SMS 발송 — 네이버 클라우드 SENS API
    카카오 알림톡 실패 Failover 또는 단독 발송용
    """
    if not settings.NAVER_SENS_SERVICE_ID:
        return {"success": False, "reason": "SENS not configured"}

    service_id = settings.NAVER_SENS_SERVICE_ID
    uri = f"/sms/v2/services/{service_id}/messages"
    timestamp = str(int(time.time() * 1000))
    signature = _make_sens_signature("POST", uri, timestamp)

    payload = {
        "type": "SMS",
        "from": settings.NAVER_SENS_SENDER,
        "content": message,
        "messages": [{"to": phone.replace("-", "")}],
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://sens.apigw.ntruss.com{uri}",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "x-ncp-apigw-timestamp": timestamp,
                "x-ncp-iam-access-key": settings.NAVER_SENS_ACCESS_KEY,
                "x-ncp-apigw-signature-v2": signature,
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


def _make_sens_signature(method: str, uri: str, timestamp: str) -> str:
    """NAVER Cloud SENS HMAC-SHA256 서명 생성"""
    message = f"{method} {uri}\n{timestamp}\n{settings.NAVER_SENS_ACCESS_KEY}"
    raw_hmac = hmac.new(
        settings.NAVER_SENS_SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(raw_hmac).decode("utf-8")


# ── Web Push (VAPID) ──────────────────────────────────────────────────────────

async def send_web_push_to_user(
    db,
    user_id: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> None:
    """
    사용자의 모든 Web Push 구독에 VAPID 알림 발송.
    pywebpush 패키지 필요: pip install pywebpush
    """
    from sqlalchemy import text as sql_text
    result = await db.execute(
        sql_text("SELECT endpoint, p256dh_key, auth_key FROM push_subscriptions WHERE user_id = :uid"),
        {"uid": user_id},
    )
    subscriptions = result.fetchall()
    if not subscriptions:
        return

    payload = json.dumps({"title": title, "body": body, **(data or {})})
    tasks = [
        _send_vapid_push(row.endpoint, row.p256dh_key, row.auth_key, payload)
        for row in subscriptions
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _send_vapid_push(endpoint: str, p256dh: str, auth: str, payload: str) -> None:
    try:
        from pywebpush import webpush, WebPushException
        webpush(
            subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": "mailto:admin@sepang.kr"},
        )
    except Exception:
        pass
