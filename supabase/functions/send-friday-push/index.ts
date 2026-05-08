/**
 * Edge Function — 금요일 Night 프로모션 푸시
 * 매주 금요일 20:00 KST (11:00 UTC) GitHub Actions에서 호출
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

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

Deno.serve(async () => {
  const projectId = (() => {
    try { return JSON.parse(Deno.env.get("FCM_SERVICE_ACCOUNT_JSON") ?? "{}").project_id ?? ""; }
    catch { return ""; }
  })();

  // Night 서비스 이용 이력 고객 (최대 5,000명)
  const { data: users } = await supabase
    .from("users")
    .select(`
      id, name, fcm_token,
      orders!inner(service_type)
    `)
    .eq("orders.service_type", "NIGHT")
    .not("fcm_token", "is", null)
    .limit(5000);

  const fcmToken = await getFcmToken();
  let sent = 0;

  // 중복 제거
  const unique = [...new Map((users ?? []).map(u => [u.id, u])).values()];

  for (const user of unique) {
    if (!user.fcm_token || !fcmToken || !projectId) continue;
    await fetch(`https://fcm.googleapis.com/v1/projects/${projectId}/messages:send`, {
      method: "POST",
      headers: { Authorization: `Bearer ${fcmToken}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        message: {
          token: user.fcm_token,
          notification: {
            title: "🌙 주말 전 Night 빨래 맡기세요",
            body: "오후 9시 수거 → 내일 아침 배송. 깔끔한 주말 시작!",
          },
          data: { type: "NIGHT_PROMO" },
        },
      }),
    });
    sent++;
  }

  return new Response(JSON.stringify({ ok: true, sent }), {
    headers: { "Content-Type": "application/json" },
  });
});
