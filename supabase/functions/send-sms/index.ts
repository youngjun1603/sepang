/**
 * Supabase Edge Function — NAVER SENS SMS 발송
 * 호출: POST /functions/v1/send-sms
 * Body: { phone: string, message: string }
 * 인증: Authorization: Bearer <SUPABASE_ANON_KEY>  (supabase-secret 헤더로 검증)
 */
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { crypto } from "https://deno.land/std@0.168.0/crypto/mod.ts";
import { encodeBase64 } from "https://deno.land/std@0.168.0/encoding/base64.ts";

const SERVICE_ID  = Deno.env.get("NAVER_SENS_SERVICE_ID") ?? "";
const ACCESS_KEY  = Deno.env.get("NAVER_SENS_ACCESS_KEY")  ?? "";
const SECRET_KEY  = Deno.env.get("NAVER_SENS_SECRET_KEY")  ?? "";
const SENDER      = Deno.env.get("NAVER_SENS_SENDER")       ?? "";

async function hmacSha256(key: string, message: string): Promise<string> {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(key);
  const msgData = encoder.encode(message);
  const cryptoKey = await crypto.subtle.importKey(
    "raw", keyData, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", cryptoKey, msgData);
  return encodeBase64(new Uint8Array(sig));
}

serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  const { phone, message } = await req.json();
  if (!phone || !message) {
    return new Response(JSON.stringify({ error: "phone and message required" }), {
      status: 400, headers: { "Content-Type": "application/json" },
    });
  }

  const timestamp = Date.now().toString();
  const method = "POST";
  const url = `/sms/v2/services/${SERVICE_ID}/messages`;
  const stringToSign = `${method} ${url}\n${timestamp}\n${ACCESS_KEY}`;
  const signature = await hmacSha256(SECRET_KEY, stringToSign);

  const body = JSON.stringify({
    type: "SMS",
    from: SENDER,
    content: message,
    messages: [{ to: phone.replace(/-/g, "") }],
  });

  const resp = await fetch(`https://sens.apigw.ntruss.com${url}`, {
    method: "POST",
    headers: {
      "Content-Type":          "application/json",
      "x-ncp-apigw-timestamp": timestamp,
      "x-ncp-iam-access-key":  ACCESS_KEY,
      "x-ncp-apigw-signature-v2": signature,
    },
    body,
  });

  const result = await resp.json();
  return new Response(JSON.stringify(result), {
    status: resp.ok ? 200 : 502,
    headers: { "Content-Type": "application/json" },
  });
});
