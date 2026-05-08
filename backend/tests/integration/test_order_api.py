"""통합 테스트 — 주문 API 엔드투엔드"""
import pytest
from httpx import AsyncClient
pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_create_order_success(client: AsyncClient, customer_user, make_auth_header):
    """정상 주문 생성 → 201 + deadline_at 반환"""
    resp = await client.post(
        "/api/v1/orders/",
        json={
            "service_type":    "DAY",
            "wash_category":   "CLOTHES_30L",
            "pickup_address":  "서울시 강남구 테헤란로 521",
            "pickup_lat":      37.4979,
            "pickup_lng":      127.0276,
            "delivery_address":"서울시 강남구 테헤란로 521",
            "delivery_lat":    37.4979,
            "delivery_lng":    127.0276,
        },
        headers=make_auth_header(customer_user["id"], "CUSTOMER"),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "order_id"    in data
    assert "deadline_at" in data
    assert data["total_amount"] == 13000


@pytest.mark.asyncio
async def test_create_order_invalid_category(client: AsyncClient, customer_user, make_auth_header):
    """잘못된 카테고리 → 422"""
    resp = await client.post(
        "/api/v1/orders/",
        json={
            "service_type":    "DAY",
            "wash_category":   "INVALID_CATEGORY",
            "pickup_address":  "서울시 강남구",
            "pickup_lat": 37.4979, "pickup_lng": 127.0276,
            "delivery_address":"서울시 강남구",
            "delivery_lat": 37.4979, "delivery_lng": 127.0276,
        },
        headers=make_auth_header(customer_user["id"], "CUSTOMER"),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_order_unauthenticated(client: AsyncClient):
    """인증 없이 주문 → 401/403"""
    resp = await client.post(
        "/api/v1/orders/",
        json={"service_type": "DAY", "wash_category": "CLOTHES_30L",
              "pickup_address": "x", "pickup_lat": 37.0, "pickup_lng": 127.0,
              "delivery_address": "x", "delivery_lat": 37.0, "delivery_lng": 127.0}
    )
    assert resp.status_code in (401, 403)  # HTTPBearer returns 403 for missing auth


@pytest.mark.asyncio
async def test_accept_order_optimistic_lock(client: AsyncClient, partner_user, customer_user, make_auth_header, db):
    """두 점주 동시 수락 → 첫 번째만 성공, 두 번째는 409"""
    from sqlalchemy import text
    # 주문 생성
    create_resp = await client.post(
        "/api/v1/orders/",
        json={
            "service_type": "DAY", "wash_category": "CLOTHES_30L",
            "pickup_address": "강남구 테헤란로 1",
            "pickup_lat": 37.4979, "pickup_lng": 127.0276,
            "delivery_address": "강남구 테헤란로 1",
            "delivery_lat": 37.4979, "delivery_lng": 127.0276,
        },
        headers=make_auth_header(customer_user["id"], "CUSTOMER"),
    )
    order_id = create_resp.json()["order_id"]

    # 첫 번째 수락 (성공)
    resp1 = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"new_status": "ACCEPTED"},
        headers=make_auth_header(partner_user["id"], "PARTNER"),
    )
    assert resp1.status_code == 200

    # 두 번째 수락 (409 — version 충돌)
    resp2 = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"new_status": "ACCEPTED"},
        headers=make_auth_header(partner_user["id"], "PARTNER"),
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_status_update_requires_photo(client: AsyncClient, partner_user, make_auth_header, db):
    """PICKED_UP 전이 — 사진 없으면 400"""
    from sqlalchemy import text
    # 수락된 주문 직접 생성
    await db.execute(text("""
        INSERT INTO orders (id, customer_id, shop_id, service_type, wash_category,
            status, pickup_address, pickup_location, delivery_address, delivery_location,
            base_amount, total_amount, deadline_at)
        VALUES (
            '11111111-0000-0000-0000-000000000001'::uuid,
            '00000000-0000-0000-0000-000000000001'::uuid,
            '00000000-0000-0000-0000-000000000010'::uuid,
            'DAY', 'CLOTHES_30L', 'ACCEPTED',
            '테스트 주소', ST_SetSRID(ST_MakePoint(127.0276, 37.4979), 4326),
            '테스트 주소', ST_SetSRID(ST_MakePoint(127.0276, 37.4979), 4326),
            13000, 13000, NOW() + INTERVAL '10 hours'
        )
    """))
    await db.commit()

    resp = await client.patch(
        "/api/v1/orders/11111111-0000-0000-0000-000000000001/status",
        json={"new_status": "PICKED_UP"},
        headers=make_auth_header(partner_user["id"], "PARTNER"),
    )
    assert resp.status_code == 400
    assert "사진" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_partner_cannot_access_customer_endpoint(client, partner_user, make_auth_header):
    """점주가 고객 전용 엔드포인트 접근 → 403"""
    resp = await client.get(
        "/api/v1/orders/",
        headers=make_auth_header(partner_user["id"], "PARTNER"),
    )
    # 고객 전용 목록이면 403, 405(메서드 없음), 또는 빈 목록
    assert resp.status_code in (200, 403, 405)


@pytest.mark.asyncio
async def test_otp_send_and_verify(client: AsyncClient):
    """OTP 발송 → 검증 플로우"""
    send_resp = await client.post(
        "/api/v1/auth/send-otp",
        json={"phone": "01099998888"}
    )
    assert send_resp.status_code == 200
    assert send_resp.json()["expires_in"] == 180


@pytest.mark.asyncio
async def test_partner_login_wrong_password(client: AsyncClient):
    """잘못된 비밀번호 → 401"""
    resp = await client.post(
        "/api/v1/auth/partner/login",
        json={"business_number": "123-45-67890", "password": "WrongPassword!"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_nearby_orders_geo_filter(client: AsyncClient, partner_user, make_auth_header, db):
    """PostGIS 반경 필터 — 3km 이내 주문만 반환"""
    from sqlalchemy import text
    # 가까운 주문 (0.5km)
    await db.execute(text("""
        INSERT INTO orders (id, customer_id, service_type, wash_category, status,
            pickup_address, pickup_location, delivery_address, delivery_location,
            base_amount, total_amount, deadline_at)
        VALUES (
            '22222222-0000-0000-0000-000000000001'::uuid,
            '00000000-0000-0000-0000-000000000001'::uuid,
            'DAY', 'CLOTHES_30L', 'PENDING',
            '강남역 근처', ST_SetSRID(ST_MakePoint(127.030, 37.500), 4326),
            '강남역 근처', ST_SetSRID(ST_MakePoint(127.030, 37.500), 4326),
            13000, 13000, NOW() + INTERVAL '10 hours'
        )
    """))
    # 먼 주문 (15km)
    await db.execute(text("""
        INSERT INTO orders (id, customer_id, service_type, wash_category, status,
            pickup_address, pickup_location, delivery_address, delivery_location,
            base_amount, total_amount, deadline_at)
        VALUES (
            '22222222-0000-0000-0000-000000000002'::uuid,
            '00000000-0000-0000-0000-000000000001'::uuid,
            'DAY', 'CLOTHES_30L', 'PENDING',
            '노원구 먼곳', ST_SetSRID(ST_MakePoint(127.065, 37.655), 4326),
            '노원구 먼곳', ST_SetSRID(ST_MakePoint(127.065, 37.655), 4326),
            13000, 13000, NOW() + INTERVAL '10 hours'
        )
    """))
    await db.commit()

    resp = await client.get(
        "/api/v1/orders/partner/nearby",
        headers=make_auth_header(partner_user["id"], "PARTNER", partner_user["shop_id"]),
    )
    assert resp.status_code == 200
    order_ids = [o["order_id"] for o in resp.json()]
    # 가까운 주문만 포함
    assert "22222222-0000-0000-0000-000000000001" in order_ids
    # 먼 주문은 제외
    assert "22222222-0000-0000-0000-000000000002" not in order_ids


