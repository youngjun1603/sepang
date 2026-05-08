/**
 * Edge Function — SLA 위반 감시
 * 5분마다 GitHub Actions cron에서 호출
 * - 마감 2시간 이내: 점주 FCM 경고
 * - 마감 초과: 환불 포인트 자동 적립
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

const FCM_SA = Deno.env.get("FCM_SERVICE_ACCOUNT_JSON") ?? "";

async function getFcmAccessToken(): Promise<string | null> {
  if (!FCM_SA) return null;
  try {
    const sa = JSON.parse(FCM_SA);
    // Google OAuth2 JWT assertion
    const now = Math.floor(Date.now() / 1000);
    const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
    const payload = btoa(JSON.stringify({
      iss: sa.client_email,
      scope: "https://www.googleapis.com/auth/firebase.messaging",
      aud: "https://oauth2.googleapis.com/token",
      iat: now,
      exp: now + 3600,
    }));
    // Deno의 SubtleCrypto로 RS256 서명
    const pemKey = sa.private_key.replace(/\\n/g, "\n");
    const binaryKey = Uint8Array.from(
      atob(pemKey.replace(/-----[^-]+-----/g, "").replace(/\s/g, "")),
      (c) => c.charCodeAt(0),
    );
    const cryptoKey = await crypto.subtle.importKey(
      "pkcs8", binaryKey.buffer,
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false, ["sign"],
    );
    const sigInput = new TextEncoder().encode(`${header}.${payload}`);
    const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", cryptoKey, sigInput);
    const jwt = `${header}.${payload}.${btoa(String.fromCharCode(...new Uint8Array(sig)))}`;

    const tokenResp = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion=${jwt}`,
    });
    const { access_token } = await tokenResp.json();
    return access_token ?? null;
  } catch {
    return null;
  }
}

async function sendFcm(fcmToken: string, title: string, body: string, data: Record<string, string> = {}) {
  const token = await getFcmAccessToken();
  if (!token || !fcmToken) return;
  const sa = JSON.parse(FCM_SA);
  await fetch(`https://fcm.googleapis.com/v1/projects/${sa.project_id}/messages:send`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      message: { token: fcmToken, notification: { title, body }, data },
    }),
  });
}

Deno.serve(async () => {
  // 위험 주문 조회 (마감 4시간 이내, 미완료)
  const { data: atRisk, error } = await supabase.rpc("get_sla_at_risk_orders");
  if (error) {
    // vw_sla_at_risk 뷰 직접 조회 fallback
    const { data: rows } = await supabase
      .from("orders")
      .select(`
        id, deadline_at, status, shop_id,
        shops!inner(owner_id, users!inner(fcm_token)),
        customers:users!customer_id(phone)
      `)
      .in("status", ["ACCEPTED", "PICKED_UP", "WASHING", "DRYING", "DELIVERING"])
      .lt("deadline_at", new Date(Date.now() + 4 * 3600 * 1000).toISOString());

    const results = { warned: 0, breached: 0 };
    const now = Date.now();

    for (const order of (rows ?? [])) {
      const deadline = new Date(order.deadline_at).getTime();
      const hoursLeft = (deadline - now) / 3600000;
      const fcmToken = order.shops?.users?.fcm_token;

      if (hoursLeft < 0) {
        // SLA 위반 — 환불 포인트 적립
        const delayHours = Math.abs(hoursLeft);
        const { data: orderDetail } = await supabase
          .from("orders").select("total_amount, customer_id").eq("id", order.id).single();
        if (orderDetail) {
          const refundRate = Math.min(delayHours * 0.1, 1.0);
          const refundAmount = Math.floor(orderDetail.total_amount * refundRate);
          if (refundAmount > 0) {
            await supabase.from("point_transactions").insert({
              user_id: orderDetail.customer_id,
              amount: refundAmount,
              reason: "SLA_BREACH_REFUND",
              order_id: order.id,
            });
          }
        }
        results.breached++;
      } else if (hoursLeft < 2 && fcmToken) {
        // 마감 2시간 이내 경고
        await sendFcm(
          fcmToken,
          "⚠️ SLA 마감 임박",
          `배송 마감까지 ${hoursLeft.toFixed(1)}시간 남았습니다. 즉시 배송해 주세요.`,
          { order_id: order.id, type: "SLA_WARNING" },
        );
        results.warned++;
      }
    }

    return new Response(JSON.stringify({ ok: true, ...results }), {
      headers: { "Content-Type": "application/json" },
    });
  }

  return new Response(JSON.stringify({ ok: true, checked: atRisk?.length ?? 0 }), {
    headers: { "Content-Type": "application/json" },
  });
});
