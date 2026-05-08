/**
 * Edge Function — D+3 미주문 고객 리마인드
 * 매일 09:00 KST (00:00 UTC) GitHub Actions에서 호출
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);
const FCM_PROJECT_ID = (() => {
  try { return JSON.parse(Deno.env.get("FCM_SERVICE_ACCOUNT_JSON") ?? "{}").project_id ?? ""; }
  catch { return ""; }
})();

async function getFcmToken(): Promise<string | null> {
  const sa_str = Deno.env.get("FCM_SERVICE_ACCOUNT_JSON") ?? "";
  if (!sa_str) return null;
  try {
    const sa = JSON.parse(sa_str);
    const now = Math.floor(Date.now() / 1000);
    const header  = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
    const payload = btoa(JSON.stringify({
      iss: sa.client_email,
      scope: "https://www.googleapis.com/auth/firebase.messaging",
      aud: "https://oauth2.googleapis.com/token",
      iat: now, exp: now + 3600,
    }));
    const pem = sa.private_key.replace(/\\n/g, "\n");
    const der = Uint8Array.from(atob(pem.replace(/-----[^-]+-----/g, "").replace(/\s/g, "")), c => c.charCodeAt(0));
    const key = await crypto.subtle.importKey("pkcs8", der.buffer, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
    const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(`${header}.${payload}`));
    const jwt = `${header}.${payload}.${btoa(String.fromCharCode(...new Uint8Array(sig)))}`;
    const res = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=${jwt}`,
    });
    return (await res.json()).access_token ?? null;
  } catch { return null; }
}

async function sendFcm(fcmToken: string, title: string, body: string, data: Record<string, string> = {}) {
  const token = await getFcmToken();
  if (!token || !fcmToken || !FCM_PROJECT_ID) return;
  await fetch(`https://fcm.googleapis.com/v1/projects/${FCM_PROJECT_ID}/messages:send`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ message: { token: fcmToken, notification: { title, body }, data } }),
  });
}

Deno.serve(async () => {
  // 가입 3일 경과 & 첫 주문 없는 고객
  const threeDaysAgo = new Date();
  threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
  const dateStr = threeDaysAgo.toISOString().split("T")[0];

  const { data: users } = await supabase
    .from("users")
    .select("id, name, fcm_token")
    .eq("role", "CUSTOMER")
    .gte("created_at", `${dateStr}T00:00:00Z`)
    .lte("created_at", `${dateStr}T23:59:59Z`)
    .not("fcm_token", "is", null);

  let sent = 0;
  for (const user of (users ?? [])) {
    // 주문 내역 확인
    const { count } = await supabase
      .from("orders")
      .select("id", { count: "exact", head: true })
      .eq("customer_id", user.id);

    if (count && count > 0) continue;

    await sendFcm(
      user.fcm_token,
      "🧺 아직 첫 주문 안 하셨나요?",
      "지금 주문하면 3,000원 즉시 할인! 12시간 이내 배송 완료.",
      { type: "D3_REMINDER" },
    );
    sent++;
  }

  return new Response(JSON.stringify({ ok: true, sent }), {
    headers: { "Content-Type": "application/json" },
  });
});
