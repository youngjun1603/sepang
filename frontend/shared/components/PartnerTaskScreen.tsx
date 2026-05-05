/**
 * PartnerTaskScreen — 점주 작업 화면
 * 상태 전이 + 사진 업로드 + WebSocket 완전 연동
 */
"use client";
import { useState, useRef } from "react";
import { useNearbyOrders, usePhotoUpload } from "../hooks/useOrder";
import type { OrderStatus } from "../lib/api-client";

const STEPS: { status: OrderStatus; label: string; icon: string; requiresPhoto?: "PICKUP"|"DELIVERY" }[] = [
  { status: "PICKED_UP",  label: "수거 완료", icon: "🧺", requiresPhoto: "PICKUP" },
  { status: "WASHING",    label: "세탁 시작", icon: "🫧" },
  { status: "DRYING",     label: "건조 완료", icon: "💨" },
  { status: "DELIVERING", label: "배송 시작", icon: "🚗" },
  { status: "COMPLETED",  label: "배송 완료", icon: "✅", requiresPhoto: "DELIVERY" },
];

const STATUS_ORDER: OrderStatus[] = [
  "PENDING","ACCEPTED","PICKED_UP","WASHING","DRYING","DELIVERING","COMPLETED"
];

export default function PartnerTaskScreen({ orderId }: { orderId: string }) {
  const { orders, updateStatus } = useNearbyOrders();
  const order = orders.find((o: any) => o.order_id === orderId);

  const { upload, uploading, uploaded, error: uploadError } = usePhotoUpload(orderId);
  const [actionError, setActionError] = useState<string | null>(null);
  const [processing,  setProcessing]  = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingPhotoType, setPendingPhotoType] = useState<"PICKUP"|"DELIVERY"|null>(null);

  if (!order) return <div style={{ padding: 24, color: "#888" }}>주문을 찾을 수 없습니다</div>;

  const currentStatusIdx = STATUS_ORDER.indexOf(order.status ?? "ACCEPTED");

  const handleStepClick = async (step: typeof STEPS[number]) => {
    setActionError(null);
    // 사진 필수 체크
    if (step.requiresPhoto && !uploaded[step.requiresPhoto]) {
      setPendingPhotoType(step.requiresPhoto);
      fileInputRef.current?.click();
      return;
    }
    setProcessing(true);
    try {
      await updateStatus(orderId, step.status);
    } catch (e: any) {
      setActionError(e.message);
    } finally {
      setProcessing(false);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !pendingPhotoType) return;
    try {
      await upload(pendingPhotoType, file);
      setPendingPhotoType(null);
    } catch { /* error shown via hook */ }
    e.target.value = "";
  };

  const stepIdx = (s: OrderStatus) => STATUS_ORDER.indexOf(s);

  return (
    <div style={s.container}>
      {/* 숨겨진 파일 인풋 */}
      <input ref={fileInputRef} type="file" accept="image/*" capture="environment"
        style={{ display: "none" }} onChange={handleFileChange} />

      {/* 주문 정보 카드 */}
      <div style={s.orderCard}>
        <div style={s.orderId}>{orderId.slice(0,8).toUpperCase()}</div>
        <div style={s.orderAddr}>{order.pickup_address}</div>
        <div style={s.orderMeta}>{order.wash_category} · {order.service_type} · {order.total_amount?.toLocaleString()}원</div>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <button style={s.navBtn}>🗺️ 내비게이션</button>
          <button style={s.chatBtn}>💬 고객 채팅</button>
        </div>
      </div>

      {/* 에러 */}
      {(actionError || uploadError) && (
        <div style={s.errorBox}>{actionError ?? uploadError}</div>
      )}

      {/* 작업 단계 */}
      <div style={s.section}>
        <div style={s.sectionTitle}>작업 단계</div>
        <div style={s.stepsGrid}>
          {STEPS.map((step) => {
            const done    = stepIdx(step.status) <= currentStatusIdx;
            const active  = stepIdx(step.status) === currentStatusIdx + 1;
            const locked  = stepIdx(step.status) > currentStatusIdx + 1;
            const cls = done ? "done" : active ? "active" : "pending";
            return (
              <button
                key={step.status}
                disabled={locked || processing || done}
                style={{
                  ...s.stepBtn,
                  ...(done   ? s.stepDone   : {}),
                  ...(active ? s.stepActive : {}),
                  ...(locked ? s.stepLocked : {}),
                  cursor: (locked || done) ? "default" : "pointer",
                }}
                onClick={() => !done && !locked && handleStepClick(step)}
              >
                <div style={{ fontSize: 22, marginBottom: 5 }}>{step.icon}</div>
                {done ? "✅ " : ""}{step.label}
                {step.requiresPhoto && (
                  <div style={{ fontSize: 10, marginTop: 3, opacity: 0.7 }}>
                    {uploaded[step.requiresPhoto] ? "📷 업로드 완료" : "📷 사진 필수"}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 증빙 사진 */}
      <div style={s.section}>
        <div style={s.sectionTitle}>📷 증빙 사진</div>
        <div style={{ display: "flex", gap: 10 }}>
          {(["PICKUP","DELIVERY"] as const).map((type) => (
            <button
              key={type}
              style={{ ...s.photoBtn, ...(uploaded[type] ? s.photoBtnDone : {}) }}
              onClick={() => { setPendingPhotoType(type); fileInputRef.current?.click(); }}
              disabled={uploading[type]}
            >
              {uploading[type] ? (
                <span style={{ fontSize: 12 }}>업로드 중...</span>
              ) : uploaded[type] ? (
                <><div style={{ fontSize: 22 }}>✅</div><div style={{ fontSize: 11, color: "#2E7D32" }}>완료</div></>
              ) : (
                <><div style={{ fontSize: 22 }}>📷</div><div style={{ fontSize: 11, color: "#888" }}>{type === "PICKUP" ? "수거 시" : "배송 완료"}</div><div style={{ fontSize: 10, color: "#FF3D00", marginTop: 2 }}>필수</div></>
              )}
            </button>
          ))}
        </div>
        <div style={s.photoNote}>사진은 촬영 시각·GPS 위치가 자동 기록됩니다</div>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  container:   { maxWidth: 430, margin: "0 auto", background: "#F5F7FA", minHeight: "100vh", fontFamily: "'Noto Sans KR', sans-serif", paddingBottom: 80 },
  orderCard:   { background: "white", padding: 16, margin: "12px 12px 0", borderRadius: 13, boxShadow: "0 2px 8px rgba(0,0,0,.06)" },
  orderId:     { fontFamily: "monospace", fontSize: 11, color: "#888", marginBottom: 4 },
  orderAddr:   { fontSize: 14, fontWeight: 700, marginBottom: 2 },
  orderMeta:   { fontSize: 11, color: "#888" },
  navBtn:      { flex: 1, background: "#111", color: "white", border: "none", borderRadius: 9, padding: "9px 0", fontSize: 12, fontWeight: 700, cursor: "pointer" },
  chatBtn:     { flex: 1, background: "#EEF3FF", color: "#0057FF", border: "none", borderRadius: 9, padding: "9px 0", fontSize: 12, fontWeight: 700, cursor: "pointer" },
  errorBox:    { margin: "10px 12px 0", background: "#FFF0ED", border: "1px solid #FFCDD2", borderRadius: 9, padding: "10px 13px", fontSize: 12, color: "#C62828" },
  section:     { margin: "12px 12px 0" },
  sectionTitle:{ fontSize: 11, color: "#666", fontWeight: 700, textTransform: "uppercase" as any, letterSpacing: "0.5px", marginBottom: 8 },
  stepsGrid:   { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 9 },
  stepBtn:     { padding: "15px 10px", borderRadius: 12, textAlign: "center" as any, fontSize: 13, fontWeight: 700, border: "2px solid #E8E8E8", background: "#F5F7FA", color: "#888" },
  stepDone:    { background: "#0057FF", color: "white", borderColor: "#0057FF" },
  stepActive:  { background: "#EEF3FF", color: "#0057FF", borderColor: "#0057FF" },
  stepLocked:  { opacity: 0.5 },
  photoBtn:    { flex: 1, background: "#F5F7FA", border: "2px dashed #E8E8E8", borderRadius: 10, height: 100, display: "flex", flexDirection: "column" as any, alignItems: "center", justifyContent: "center", gap: 4, cursor: "pointer" },
  photoBtnDone:{ borderStyle: "solid", borderColor: "#00C853", background: "#E8F5E9" },
  photoNote:   { fontSize: 11, color: "#0057FF", background: "#EEF3FF", borderRadius: 9, padding: "8px 12px", marginTop: 8 },
};
