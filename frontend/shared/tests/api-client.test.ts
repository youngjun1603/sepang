import { describe, it, expect, beforeEach, vi } from "vitest";
import { tokenStore, ApiError } from "../lib/api-client";

describe("tokenStore", () => {
  beforeEach(() => localStorage.clear());

  it("토큰 저장 및 조회", () => {
    tokenStore.set("access_123", "refresh_456");
    expect(tokenStore.get()).toBe("access_123");
    expect(tokenStore.getRefresh()).toBe("refresh_456");
  });

  it("토큰 삭제", () => {
    tokenStore.set("access_123", "refresh_456");
    tokenStore.clear();
    expect(tokenStore.get()).toBeNull();
    expect(tokenStore.getRefresh()).toBeNull();
  });

  it("SSR 환경(window 없음)에서 null 반환", () => {
    const origWindow = global.window;
    // @ts-expect-error
    delete global.window;
    expect(tokenStore.get()).toBeNull();
    global.window = origWindow;
  });
});

describe("ApiError", () => {
  it("status와 detail을 포함한 에러 생성", () => {
    const err = new ApiError(404, "주문을 찾을 수 없습니다");
    expect(err.status).toBe(404);
    expect(err.detail).toBe("주문을 찾을 수 없습니다");
    expect(err.message).toBe("주문을 찾을 수 없습니다");
    expect(err instanceof Error).toBe(true);
  });
});

describe("apiFetch", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("성공 응답 JSON 반환", async () => {
    const { apiFetch } = await import("../lib/api-client");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ order_id: "test-123", total_amount: 13000 }),
    } as Response);

    const result = await apiFetch("/api/v1/orders/test-123", { skipAuth: true });
    expect(result).toEqual({ order_id: "test-123", total_amount: 13000 });
  });

  it("204 응답에서 undefined 반환", async () => {
    const { apiFetch } = await import("../lib/api-client");
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => ({}),
    } as Response);

    const result = await apiFetch("/api/v1/orders/test-123/status", { skipAuth: true });
    expect(result).toBeUndefined();
  });

  it("4xx 응답에서 ApiError 던짐", async () => {
    const { apiFetch } = await import("../lib/api-client");
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "유효하지 않은 요청입니다" }),
    } as Response);

    await expect(apiFetch("/api/v1/orders/", { skipAuth: true })).rejects.toThrow(ApiError);
  });

  it("Authorization 헤더에 Bearer 토큰 포함", async () => {
    const { apiFetch } = await import("../lib/api-client");
    tokenStore.set("my-access-token", "refresh");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({}),
    } as Response);
    global.fetch = mockFetch;

    await apiFetch("/api/v1/users/me");
    const [, options] = mockFetch.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.get("Authorization")).toBe("Bearer my-access-token");
  });
});
