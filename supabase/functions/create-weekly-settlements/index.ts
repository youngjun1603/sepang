/**
 * Edge Function — 주간 정산 자동 생성
 * 매주 월요일 01:00 KST (일요일 16:00 UTC) GitHub Actions에서 호출
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
);

Deno.serve(async () => {
  const today = new Date();
  // 지난 주 월~일 기간 계산
  const dayOfWeek = today.getDay(); // 0=일, 1=월
  const daysToLastSunday = dayOfWeek === 0 ? 7 : dayOfWeek;
  const periodEnd = new Date(today);
  periodEnd.setDate(today.getDate() - daysToLastSunday);
  periodEnd.setHours(23, 59, 59, 999);

  const periodStart = new Date(periodEnd);
  periodStart.setDate(periodEnd.getDate() - 6);
  periodStart.setHours(0, 0, 0, 0);

  // 활성 점포 목록
  const { data: shops, error: shopErr } = await supabase
    .from("shops")
    .select("id")
    .eq("is_active", true);

  if (shopErr) {
    return new Response(JSON.stringify({ ok: false, error: shopErr.message }), {
      status: 500, headers: { "Content-Type": "application/json" },
    });
  }

  let created = 0;
  const errors: string[] = [];

  for (const shop of (shops ?? [])) {
    // 해당 기간 완료 주문 집계
    const { data: orders } = await supabase
      .from("orders")
      .select("total_amount, platform_fee")
      .eq("shop_id", shop.id)
      .eq("status", "COMPLETED")
      .gte("completed_at", periodStart.toISOString())
      .lte("completed_at", periodEnd.toISOString());

    if (!orders || orders.length === 0) continue;

    const grossAmount = orders.reduce((s, o) => s + o.total_amount, 0);
    const totalFee    = orders.reduce((s, o) => s + o.platform_fee, 0);
    const netAmount   = grossAmount - totalFee;

    // 중복 방지: 같은 기간 정산이 없는 경우만 생성
    const { data: existing } = await supabase
      .from("settlements")
      .select("id")
      .eq("shop_id", shop.id)
      .eq("period_start", periodStart.toISOString().split("T")[0])
      .single();

    if (existing) continue;

    const { error: insertErr } = await supabase.from("settlements").insert({
      shop_id:      shop.id,
      period_start: periodStart.toISOString().split("T")[0],
      period_end:   periodEnd.toISOString().split("T")[0],
      order_count:  orders.length,
      gross_amount: grossAmount,
      platform_fee: totalFee,
      net_amount:   netAmount,
      status:       "PENDING",
    });

    if (insertErr) {
      errors.push(`${shop.id}: ${insertErr.message}`);
    } else {
      created++;
    }
  }

  return new Response(
    JSON.stringify({
      ok: true,
      period: `${periodStart.toISOString().split("T")[0]} ~ ${periodEnd.toISOString().split("T")[0]}`,
      created,
      errors,
    }),
    { headers: { "Content-Type": "application/json" } },
  );
});
