import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useOrder } from "../hooks/useOrder";

const mockOrder = {
  id: "order-abc",
  status: "WASHING",
  service_type: "DAY",
  wash_category: "CLOTHES_30L",
  pickup_address: "강남구 테헤란로 521",
  delivery_address: "서초구 방배동 123",
  total_amount: 13000,
  platform_fee: 1000,
  customer_id: "user-001",
  ordered_at: new Date().toISOString(),
  deadline_at: new Date(Date.now() + 8 * 3600 * 1000).toISOString(),
};

describe("useOrder", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    // WebSocket mock
    global.WebSocket = vi.fn().mockImplementation(() => ({
      onmessage: null, onerror: null, close: vi.fn(), readyState: 1,
    })) as unknown as typeof WebSocket;
  });

  it("주문 상세 조회", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => mockOrder,
    } as Response);

    const { result } = renderHook(() => useOrder("order-abc"));
    await waitFor(() => expect(result.current.order).not.toBeNull());
    expect(result.current.order?.id).toBe("order-abc");
    expect(result.current.order?.status).toBe("WASHING");
  });

  it("SLA 카운트다운 계산", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => mockOrder,
    } as Response);

    const { result } = renderHook(() => useOrder("order-abc"));
    await waitFor(() => expect(result.current.order).not.toBeNull());

    // hoursLeft는 deadline까지 남은 시간
    expect(result.current.hoursLeft).toBeGreaterThan(0);
    expect(result.current.hoursLeft).toBeLessThanOrEqual(8);
  });

  it("API 오류 시 error 상태 설정", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 404,
      json: async () => ({ detail: "주문을 찾을 수 없습니다" }),
    } as Response);

    const { result } = renderHook(() => useOrder("nonexistent"));
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.error).toContain("주문을 찾을 수 없습니다");
  });
});
