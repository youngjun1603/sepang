/**
 * 세팡 API 클라이언트 — Next.js 공통 레이어
 * 모든 앱(고객/점주/관리자)에서 공유
 */
import { createClient, SupabaseClient } from "@supabase/supabase-js";

const BASE_URL          = process.env.NEXT_PUBLIC_API_URL          ?? "https://api.sepang.kr";
const SUPABASE_URL      = process.env.NEXT_PUBLIC_SUPABASE_URL      ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

let _supabase: SupabaseClient | null = null;
function getSupabase(): SupabaseClient {
  if (!_supabase) _supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  return _supabase;
}

// ── 토큰 관리 (localStorage + httpOnly cookie fallback) ──────────────────────

export const tokenStore = {
  get: ()    => typeof window !== "undefined" ? localStorage.getItem("access_token")  : null,
  getRefresh: () => typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null,
  set: (access: string, refresh: string) => {
    localStorage.setItem("access_token",  access);
    localStorage.setItem("refresh_token", refresh);
  },
  clear: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },
};

// ── 기본 fetch 래퍼 ──────────────────────────────────────────────────────────

interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
  retries?:  number;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

export async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { skipAuth, retries = 1, ...init } = opts;
  const token = tokenStore.get();

  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token && !skipAuth) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  // 401 → 토큰 갱신 후 재시도
  if (res.status === 401 && retries > 0 && !skipAuth) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return apiFetch<T>(path, { ...opts, retries: retries - 1 });
    tokenStore.clear();
    window.location.href = "/login";
    throw new ApiError(401, "로그인이 필요합니다");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "서버 오류가 발생했습니다" }));
    let detail = body.detail ?? body.message ?? "오류가 발생했습니다";
    if (Array.isArray(detail)) {
      detail = detail.map((e: any) => e.msg ?? String(e)).join(", ");
    }
    throw new ApiError(res.status, String(detail));
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = tokenStore.getRefresh();
  if (!refresh) return false;
  try {
    const data = await apiFetch<{ access_token: string }>(
      `/api/v1/auth/refresh?refresh_token=${encodeURIComponent(refresh)}`,
      { method: "POST", skipAuth: true }
    );
    tokenStore.set(data.access_token, refresh);
    return true;
  } catch {
    return false;
  }
}

// ── 인증 API ─────────────────────────────────────────────────────────────────

export const authApi = {
  sendOtp: (phone: string) =>
    apiFetch<{ message: string; expires_in: number }>("/api/v1/auth/send-otp", {
      method: "POST", body: JSON.stringify({ phone }), skipAuth: true,
    }),

  verifyOtp: (phone: string, code: string, name?: string) =>
    apiFetch<{ access_token: string; refresh_token: string; user_id: string }>(
      "/api/v1/auth/verify-otp",
      { method: "POST", body: JSON.stringify({ phone, code, name }), skipAuth: true }
    ),

  partnerLogin: (business_number: string, password: string) =>
    apiFetch<{ access_token: string; refresh_token: string; shop_id: string }>(
      "/api/v1/auth/partner/login",
      { method: "POST", body: JSON.stringify({ business_number, password }), skipAuth: true }
    ),

  adminLogin: (email: string, password: string) =>
    apiFetch<{ temp_token: string }>(
      "/api/v1/auth/admin/login",
      { method: "POST", body: JSON.stringify({ email, password }), skipAuth: true }
    ),

  adminOtp: (temp_token: string, otp_code: string) =>
    apiFetch<{ access_token: string; refresh_token: string }>(
      "/api/v1/auth/admin/otp",
      { method: "POST", body: JSON.stringify({ temp_token, otp_code }), skipAuth: true }
    ),

  me: () => apiFetch<User>("/api/v1/users/me"),

  logout: () => tokenStore.clear(),

  saveFcmToken: (fcm_token: string) =>
    apiFetch<{ success: boolean }>("/api/v1/users/me/fcm-token", {
      method: "PATCH", body: JSON.stringify({ fcm_token }),
    }),

  savePushSubscription: (endpoint: string, p256dh_key: string, auth_key: string) =>
    apiFetch<{ success: boolean }>("/api/v1/users/me/push-subscription", {
      method: "POST", body: JSON.stringify({ endpoint, p256dh_key, auth_key }),
    }),
};

// ── 주문 API ─────────────────────────────────────────────────────────────────

export const orderApi = {
  create: (req: CreateOrderRequest) =>
    apiFetch<{ order_id: string; deadline_at: string; total_amount: number }>(
      "/api/v1/orders/", { method: "POST", body: JSON.stringify(req) }
    ),

  get: (id: string) =>
    apiFetch<Order>(`/api/v1/orders/${id}`),

  list: () =>
    apiFetch<Order[]>("/api/v1/orders/"),

  updateStatus: (id: string, new_status: OrderStatus, note?: string) =>
    apiFetch<{ success: boolean; status: OrderStatus }>(
      `/api/v1/orders/${id}/status`,
      { method: "PATCH", body: JSON.stringify({ new_status, note }) }
    ),

  uploadPhoto: async (orderId: string, photoType: "PICKUP" | "DELIVERY" | "ISSUE", file: File) => {
    const form = new FormData();
    form.append("file", file);
    const token = tokenStore.get();
    const res = await fetch(
      `${BASE_URL}/api/v1/orders/${orderId}/photos?photo_type=${photoType}`,
      { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form }
    );
    if (!res.ok) throw new ApiError(res.status, "사진 업로드 실패");
    return res.json() as Promise<{ storage_path: string; view_url: string }>;
  },

  nearbyOrders: () =>
    apiFetch<NearbyOrder[]>("/api/v1/orders/partner/nearby"),
};

// ── 정산 API ─────────────────────────────────────────────────────────────────

export const settlementApi = {
  list: (shopId: string) =>
    apiFetch<Settlement[]>(`/api/v1/settlements/?shop_id=${shopId}`),

  detail: (id: string) =>
    apiFetch<Settlement>(`/api/v1/settlements/${id}`),
};

// ── 관리자 API ────────────────────────────────────────────────────────────────

export const adminApi = {
  dashboard: () =>
    apiFetch<DashboardKpi>("/api/v1/admin/dashboard"),

  orders: (params?: { status?: string; page?: number }) => {
    const p: Record<string, string> = {};
    if (params?.status != null) p.status = params.status;
    if (params?.page   != null) p.page   = String(params.page);
    const qs = new URLSearchParams(p).toString();
    return apiFetch<PaginatedResponse<Order>>("/api/v1/admin/orders" + (qs ? "?" + qs : ""));
  },

  shops: () =>
    apiFetch<Shop[]>("/api/v1/admin/shops"),

  createShop: (data: CreateShopInput) =>
    apiFetch<{ id: string; name: string; lat: number; lng: number }>("/api/v1/admin/shops", {
      method: "POST", body: JSON.stringify(data),
    }),

  slaAtRisk: () =>
    apiFetch<SlaOrder[]>("/api/v1/admin/sla-at-risk"),

  settlements: (params?: { period_start?: string }) =>
    apiFetch<Settlement[]>("/api/v1/admin/settlements?" + new URLSearchParams(params as any)),

  auditLogs: () =>
    apiFetch<AuditLog[]>("/api/v1/admin/audit-logs"),

  marketing: () =>
    apiFetch<MarketingStats>("/api/v1/admin/marketing"),

  markSettlementPaid: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/v1/admin/settlements/${id}/pay`, { method: "PATCH" }),
};

// ── 리뷰 API ─────────────────────────────────────────────────────────────────

export const reviewApi = {
  create: (orderId: string, rating: number, comment?: string) =>
    apiFetch<{ id: string; message: string }>("/api/v1/reviews/", {
      method: "POST",
      body: JSON.stringify({ order_id: orderId, rating, comment }),
    }),

  listByShop: (shopId: string) =>
    apiFetch<Review[]>(`/api/v1/reviews/shop/${shopId}`),
};

// ── 주소 → 위경도 변환 API ─────────────────────────────────────────────────────

export const geocodeApi = {
  search: (address: string) =>
    apiFetch<{ lat: number; lng: number; address: string }>("/api/v1/geocode/", {
      method: "POST",
      body: JSON.stringify({ address }),
      skipAuth: true,
    }),

  vapidPublicKey: () =>
    apiFetch<{ public_key: string }>("/api/v1/geocode/vapid-public-key", { skipAuth: true }),
};

// ── 포인트 / 쿠폰 API ─────────────────────────────────────────────────────────

export const pointsApi = {
  get: () =>
    apiFetch<PointsData>("/api/v1/users/me/points"),

  coupons: () =>
    apiFetch<{ coupons: Coupon[]; count: number }>("/api/v1/users/me/coupons"),
};

// ── 세탁 품목 API ─────────────────────────────────────────────────────────────

export const washItemsApi = {
  list: () =>
    apiFetch<WashItem[]>("/api/v1/wash-items/", { skipAuth: true }),

  listAll: () =>
    apiFetch<WashItem[]>("/api/v1/wash-items/all"),

  create: (data: Omit<WashItem, "id" | "is_active" | "created_at">) =>
    apiFetch<WashItem>("/api/v1/wash-items/", {
      method: "POST", body: JSON.stringify(data),
    }),

  update: (id: string, data: Partial<Omit<WashItem, "id" | "created_at">>) =>
    apiFetch<{ success: boolean }>(`/api/v1/wash-items/${id}`, {
      method: "PATCH", body: JSON.stringify(data),
    }),

  remove: (id: string) =>
    apiFetch<{ success: boolean }>(`/api/v1/wash-items/${id}`, { method: "DELETE" }),
};

// ── 결제 API (토스페이먼츠) ────────────────────────────────────────────────────

export const paymentApi = {
  prepare: (orderId: string) =>
    apiFetch<{ client_key: string; order_id: string; amount: number; order_name: string }>(
      `/api/v1/payments/prepare/${orderId}`
    ),

  confirm: (paymentKey: string, orderId: string, amount: number) =>
    apiFetch<{ success: boolean; payment_key: string; method: string; approved_at: string; receipt_url: string }>(
      "/api/v1/payments/confirm",
      { method: "POST", body: JSON.stringify({ payment_key: paymentKey, order_id: orderId, amount }) }
    ),

  cancel: (orderId: string, cancelReason: string) =>
    apiFetch<{ success: boolean; status: string }>(
      `/api/v1/payments/${orderId}/cancel`,
      { method: "POST", body: JSON.stringify({ cancel_reason: cancelReason }) }
    ),

  status: (orderId: string) =>
    apiFetch<{ order_id: string; amount: number; payment_status: string; payment_method: string; paid_at: string }>(
      `/api/v1/payments/${orderId}`
    ),
};

// ── Supabase Realtime 실시간 주문 추적 ───────────────────────────────────────

export function createOrderTrackingSocket(
  orderId: string,
  handlers: {
    onStatus:     (status: OrderStatus) => void;
    onConnected?: () => void;
    onError?:     (e: Event) => void;
  }
): { close: () => void } {
  const supabase = getSupabase();
  const channel = supabase
    .channel(`order-${orderId}`)
    .on(
      "postgres_changes",
      { event: "UPDATE", schema: "public", table: "orders", filter: `id=eq.${orderId}` },
      (payload: { new: { status: OrderStatus } }) => {
        handlers.onStatus(payload.new.status);
      }
    )
    .subscribe((status: string) => {
      if (status === "SUBSCRIBED") handlers.onConnected?.();
    });

  return { close: () => { supabase.removeChannel(channel); } };
}

// ── 타입 정의 ─────────────────────────────────────────────────────────────────

export interface User {
  id: string; name: string; phone: string; email?: string; role: string; created_at: string;
}

export interface Order {
  id: string; customer_id: string; shop_id?: string;
  service_type: "DAY" | "NIGHT"; wash_category: string;
  status: OrderStatus; pickup_address: string; delivery_address: string;
  total_amount: number; platform_fee: number;
  ordered_at: string; deadline_at: string;
  accepted_at?: string; picked_up_at?: string; completed_at?: string;
  customer_note?: string;
}

export interface NearbyOrder {
  order_id: string; wash_category: string; service_type: "DAY"|"NIGHT";
  pickup_address: string; distance_m: number; deadline_at: string;
  total_amount: number; hours_left: number;
}

export interface Settlement {
  id: string; shop_id: string; period_start: string; period_end: string;
  order_count: number; total_sales: number; platform_fee: number;
  net_payout: number; payout_date?: string; status: string;
}

export interface Shop {
  id: string; name: string; region: string; team_type: string;
  today_orders: number; rating: number; is_active: boolean; is_available: boolean;
}

export interface CreateShopInput {
  name: string; address: string; owner_name: string;
  phone: string; business_number: string; password: string;
  team_type: "DAY" | "NIGHT" | "BOTH"; radius_km: number;
  bank_name?: string; bank_account?: string; bank_holder?: string;
}

export interface DashboardKpi {
  today_orders: number; conversion_rate: number;
  avg_order_value: number; sla_violations: number;
  week_revenue: number; active_shops: number;
}

export interface SlaOrder extends Order { hours_left: number; shop_name?: string; customer_phone: string; }
export interface AuditLog { id: number; admin_email: string; ip_address: string; path: string; action: string; created_at: string; }
export interface PaginatedResponse<T> { items: T[]; total: number; page: number; pages: number; }

export interface CreateOrderRequest {
  service_type: "DAY"|"NIGHT"; wash_category: string;
  pickup_address: string; pickup_lat: number; pickup_lng: number;
  delivery_address: string; delivery_lat: number; delivery_lng: number;
  coupon_id?: string; use_points?: boolean; customer_note?: string;
}

export interface Review {
  id: string; order_id: string; customer_name: string;
  rating: number; comment?: string; created_at: string;
}

export interface PointTransaction {
  amount: number; balance: number; reason: string; created_at: string;
}

export interface PointsData {
  balance: number;
  history: PointTransaction[];
}

export interface Coupon {
  id: string; name: string; code: string;
  discount_amount?: number; discount_rate?: number;
  min_order_amount: number; expires_at?: string;
}

export interface WashItem {
  id: string; key: string; label: string; icon: string;
  base_price: number; sort_order: number;
  is_active?: boolean; created_at?: string;
}

export interface CouponStat {
  code: string; name: string; used_count: number; issued_count: number;
}

export interface MarketingStats {
  total_customers: number; new_today: number; new_week: number; fcm_opt_in: number;
  points_issued: number; points_redeemed: number;
  coupons: CouponStat[];
  d3_target: number; night_target: number;
}

export type OrderStatus =
  | "PENDING" | "ACCEPTED" | "PICKUP_EN_ROUTE" | "PICKED_UP"
  | "WASHING" | "DRYING"   | "DELIVERING"      | "COMPLETED" | "CANCELLED";
