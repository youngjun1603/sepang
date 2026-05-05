import { test, expect } from "@playwright/test";
import { mockApi } from "./helpers";

test.describe("로그인 플로우", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("휴대폰 번호 입력 후 OTP 발송", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("세팡")).toBeVisible();

    // 전화번호 입력
    await page.fill("input[placeholder*='010']", "01012345678");
    await page.getByRole("button", { name: "인증번호 받기" }).click();

    // OTP 입력창으로 전환
    await expect(page.getByPlaceholder("인증번호 6자리")).toBeVisible();
  });

  test("OTP 입력 후 로그인 성공 → 홈 이동", async ({ page }) => {
    await page.goto("/");

    await page.fill("input[placeholder*='010']", "01012345678");
    await page.getByRole("button", { name: "인증번호 받기" }).click();

    await page.fill("input[placeholder='인증번호 6자리']", "123456");
    await page.getByRole("button", { name: "로그인" }).click();

    // 홈 화면으로 이동 확인
    await expect(page.getByText("안녕하세요")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("테스트유저")).toBeVisible();
  });

  test("짧은 전화번호는 버튼 비활성화", async ({ page }) => {
    await page.goto("/");
    await page.fill("input[placeholder*='010']", "010");
    const btn = page.getByRole("button", { name: "인증번호 받기" });
    await expect(btn).toBeDisabled();
  });
});
