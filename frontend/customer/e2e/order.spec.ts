import { test, expect } from "@playwright/test";
import { mockApi, injectAuthToken } from "./helpers";

test.describe("주문 플로우", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await injectAuthToken(page);
  });

  test("홈 화면 로드 — 서비스 선택 UI 표시", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("서비스 선택")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("당일 수령")).toBeVisible();
    await expect(page.getByText("새벽 수령")).toBeVisible();
  });

  test("주소 입력 후 지오코딩 확인", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=서비스 선택");

    await page.fill("input[placeholder*='주소']", "서울시 중구 세종대로");
    await page.getByRole("button", { name: "확인" }).click();

    // 지오코딩 성공 → mock 응답 주소 표시
    await expect(page.getByText(/세종대로/)).toBeVisible({ timeout: 5000 });
  });

  test("주문 생성 → 추적 화면 이동", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=서비스 선택");

    // 주소 입력 + 지오코딩
    await page.fill("input[placeholder*='주소']", "서울시 중구 세종대로");
    await page.getByRole("button", { name: "확인" }).click();
    await page.waitForSelector("text=/세종대로/", { timeout: 5000 });

    // 서비스 및 세탁물 선택 (기본값 유지)
    await page.getByRole("button", { name: /지금 바로 주문/ }).click();

    // 주문 접수 토스트 및 추적 화면 이동
    await expect(page.getByText("주문이 접수되었습니다")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("실시간 추적")).toBeVisible({ timeout: 5000 });
  });

  test("주소 미확인 시 오류 메시지", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=서비스 선택");

    await page.fill("input[placeholder*='주소']", "서울시 강남구");
    // 주소 확인 없이 바로 주문
    await page.getByRole("button", { name: /지금 바로 주문/ }).click();

    await expect(page.getByText("주소 확인 버튼을 눌러")).toBeVisible();
  });

  test("내 주문 목록 탭 — API 호출 후 빈 목록 표시", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("text=서비스 선택");

    await page.getByText("내주문").click();
    await expect(page.getByText("내 주문")).toBeVisible();
    await expect(page.getByText("아직 주문 내역이 없어요")).toBeVisible({ timeout: 5000 });
  });
});

test.describe("추적 화면", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
    await injectAuthToken(page);
  });

  test("추적 화면 — 주문 정보 표시", async ({ page }) => {
    // localStorage에 라우팅 파라미터 주입
    await page.addInitScript(() => {
      window.__E2E_TRACKING_ORDER_ID__ = "order-001";
    });

    await page.goto("/");
    await page.waitForSelector("text=서비스 선택");

    // 주소 입력 + 확인 + 주문
    await page.fill("input[placeholder*='주소']", "테스트 주소");
    await page.getByRole("button", { name: "확인" }).click();
    await page.waitForTimeout(1000);
    await page.getByRole("button", { name: /지금 바로 주문/ }).click();

    await expect(page.getByText("실시간 추적")).toBeVisible({ timeout: 8000 });
    await expect(page.getByText("세종대로")).toBeVisible();
  });
});
