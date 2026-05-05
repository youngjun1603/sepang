import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAuth, AuthProvider } from "../hooks/useAuth";
import { tokenStore } from "../lib/api-client";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AuthProvider>{children}</AuthProvider>
);

describe("useAuth", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("초기 상태: user=null, isAuthenticated=false", () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("login 호출 후 user가 설정된다", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true, status: 200,
      json: async () => ({ id: "u1", name: "홍길동", phone: "01012345678", role: "CUSTOMER", created_at: "" }),
    } as Response);

    tokenStore.set("access_token_abc", "refresh_token_abc");
    const { result } = renderHook(() => useAuth(), { wrapper });

    await act(async () => {
      await result.current.loginWithToken("access_token_abc", "refresh_token_abc");
    });

    expect(result.current.user?.name).toBe("홍길동");
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("logout 호출 후 user=null로 초기화된다", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => { result.current.logout(); });
    expect(result.current.user).toBeNull();
    expect(tokenStore.get()).toBeNull();
  });
});
