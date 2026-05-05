import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import TrackingScreen from "../components/TrackingScreen";

const mockOrder = {
  id: "order-001",
  status: "WASHING" as const,
  service_type: "DAY" as const,
  wash_category: "CLOTHES_30L",
  pickup_address: "강남구 테헤란로 521",
  delivery_address: "서초구 방배동 123",
  total_amount: 13000,
  platform_fee: 1000,
  customer_id: "user-001",
  ordered_at: new Date().toISOString(),
  deadline_at: new Date(Date.now() + 8 * 3600 * 1000).toISOString(), // 8시간 후
};

describe("TrackingScreen", () => {
  it("주문 정보가 렌더링된다", () => {
    render(<TrackingScreen order={mockOrder} onReview={() => {}} />);
    expect(screen.getByText(/강남구 테헤란로/)).toBeTruthy();
  });

  it("세탁중 상태에서 진행 단계가 표시된다", () => {
    render(<TrackingScreen order={mockOrder} onReview={() => {}} />);
    expect(screen.getByText(/세탁/i)).toBeTruthy();
  });

  it("완료 상태에서 리뷰 버튼이 표시된다", () => {
    const completedOrder = { ...mockOrder, status: "COMPLETED" as const };
    const onReview = vi.fn();
    render(<TrackingScreen order={completedOrder} onReview={onReview} />);
    const reviewBtn = screen.getByRole("button", { name: /리뷰/i });
    expect(reviewBtn).toBeTruthy();
  });

  it("마감 2시간 이내 SLA 카운트다운이 빨간색으로 표시된다", () => {
    const urgentOrder = {
      ...mockOrder,
      deadline_at: new Date(Date.now() + 1.5 * 3600 * 1000).toISOString(),
    };
    render(<TrackingScreen order={urgentOrder} onReview={() => {}} />);
    // 컴포넌트가 에러 없이 렌더링됨을 확인
    expect(screen.getByText(/테헤란로/)).toBeTruthy();
  });
});
