import { Page } from "@playwright/test";

/** 모든 API 호출을 mock으로 대체 */
export async function mockApi(page: Page) {
  // OTP 발송
  await page.route("**/api/v1/auth/send-otp", route =>
    route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ message: "인증번호가 발송되었습니다", expires_in: 180 }) })
  );

  // OTP 검증 → 토큰 반환
  await page.route("**/api/v1/auth/verify-otp", route =>
    route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ access_token: "test-access", refresh_token: "test-refresh", user_id: "u-001" }) })
  );

  // 내 프로필
  await page.route("**/api/v1/users/me", route =>
    route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ id: "u-001", name: "테스트유저", phone: "01012345678", role: "CUSTOMER", created_at: new Date().toISOString() }) })
  );

  // 주소 → 위경도
  await page.route("**/api/v1/geocode/**", route =>
    route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ lat: 37.5665, lng: 126.9780, address: "서울특별시 중구 세종대로 110" }) })
  );

  // 주문 생성
  await page.route("**/api/v1/orders/", async route => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 201, contentType: "application/json",
        body: JSON.stringify({ order_id: "order-001", deadline_at: new Date(Date.now() + 8 * 3600_000).toISOString(), total_amount: 13000 }) });
    } else {
      await route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify([]) });
    }
  });

  // 주문 상세
  await page.route("**/api/v1/orders/order-001", route =>
    route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({
        id: "order-001", status: "WASHING", service_type: "DAY", wash_category: "CLOTHES_30L",
        pickup_address: "서울특별시 중구 세종대로 110", delivery_address: "서울특별시 중구 세종대로 110",
        total_amount: 13000, platform_fee: 1000, customer_id: "u-001",
        ordered_at: new Date().toISOString(), deadline_at: new Date(Date.now() + 8 * 3600_000).toISOString(),
      }) })
  );

  // 포인트
  await page.route("**/api/v1/users/me/points", route =>
    route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ balance: 100, history: [] }) })
  );

  // 쿠폰
  await page.route("**/api/v1/users/me/coupons", route =>
    route.fulfill({ status: 200, contentType: "application/json",
      body: JSON.stringify({ coupons: [], count: 0 }) })
  );
}

/** localStorage에 인증 토큰 주입 (로그인 상태 가장) */
export async function injectAuthToken(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem("access_token",  "test-access");
    localStorage.setItem("refresh_token", "test-refresh");
  });
}
