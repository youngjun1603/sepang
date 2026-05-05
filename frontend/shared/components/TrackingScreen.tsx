/**
 * TrackingScreen — 고객 실시간 주문 추적
 * useOrderTracking 훅으로 WebSocket + SLA 카운트다운 통합
 */
"use client";
import { useOrderTracking } from "../hooks/useOrder";

const STATUS_STEPS = [
  { key: "PENDING",    label: "주문 접수",   icon: "📋" },
  { key: "ACCEPTED",   label: "점주 수락",   icon: "✋" },
  { key: "PICKED_UP",  label: "수거 완료",   icon: "🧺" },
  { key: "WASHING",    label: "세탁 중",     icon: "🫧" },
  { key: "DRYING",     label: "건조 중",     icon: "💨" },
  { key: "DELIVERING", label: "배송 중",     icon: "🚗" },
  { key: "COMPLETED",  label: "배송 완료",   icon: "✅" },
] as const;

const STATUS_ORDER = STATUS_STEPS.map((s) => s.key);

export default function TrackingScreen({ orderId }: { orderId: string }) {
  const { order, status, connected, timeLeft, error } = useOrderTracking(orderId);

  if (error)  return <div style={styles.error}>⚠️ {error}</div>;
  if (!order) return <div style={styles.loading}>로딩 중...</div>;

  const currentIdx = STATUS_ORDER.indexOf(status as any);
  const progress   = ((currentIdx + 1) / STATUS_ORDER.length) * 100;

  const timerColor = timeLeft.isDanger ? "#FF3D00" : timeLeft.isUrgent ? "#FF6D00" : "#FFD600";

  return (
    <div style={styles.container}>
      {/* SLA 카운트다운 헤더 */}
      <div style={{ ...styles.header, background: timeLeft.isDanger ? "#C62828" : "#003DC7" }}>
        <div style={styles.orderMeta}>
          주문 #{order.id.slice(0, 8).toUpperCase()} · {order.pickup_address}
        </div>
        <div style={{ ...styles.countdown, color: timerColor }}>
          {timeLeft.isExpired ? "⚠️ 마감 초과" : timeLeft.display}
        </div>
        <div style={styles.countdownLabel}>
          {timeLeft.isExpired ? "고객센터로 문의해 주세요" : "배송 완료까지 남은 시간"}
        </div>
        {/* 진행률 바 */}
        <div style={styles.progressBg}>
          <div style={{ ...styles.progressFill, width: `${progress}%` }} />
        </div>
      </div>

      {/* WebSocket 연결 상태 */}
      {!connected && (
        <div style={styles.wsWarning}>
          ⚡ 실시간 연결 중... (일반 새로고침으로 상태 확인 가능)
        </div>
      )}

      {/* 스텝 목록 */}
      <div style={styles.steps}>
        {STATUS_STEPS.filter((s) => s.key !== "PENDING").map((step, i) => {
          const stepIdx  = STATUS_ORDER.indexOf(step.key);
          const isDone   = stepIdx <= currentIdx;
          const isActive = stepIdx === currentIdx;
          return (
            <div key={step.key} style={{ ...styles.step, opacity: isDone ? 1 : 0.4 }}>
              <div style={{
                ...styles.stepDot,
                background:   isDone ? "#0057FF" : "transparent",
                borderColor:  isDone ? "#0057FF" : "#ddd",
                boxShadow:    isActive ? "0 0 0 6px rgba(0,87,255,.15)" : "none",
              }}>
                {isDone ? "✓" : ""}
              </div>
              {i < STATUS_STEPS.length - 2 && (
                <div style={{ ...styles.stepLine, background: isDone && stepIdx < currentIdx ? "#0057FF" : "#eee" }} />
              )}
              <div style={styles.stepContent}>
                <div style={{ ...styles.stepLabel, fontWeight: isActive ? 700 : 500 }}>
                  {step.icon} {step.label}
                </div>
                {isActive && (
                  <div style={styles.stepActive}>현재 단계</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 완료 시 리뷰 유도 */}
      {status === "COMPLETED" && (
        <div style={styles.reviewBanner}>
          <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>
            🎉 배송 완료! 리뷰를 작성하고 100P를 받으세요
          </div>
          <button style={styles.reviewBtn}>리뷰 작성하기</button>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container:     { maxWidth: 430, margin: "0 auto", minHeight: "100vh", background: "#F5F7FA", fontFamily: "'Noto Sans KR', sans-serif" },
  header:        { padding: "20px 20px 24px", color: "white" },
  orderMeta:     { fontSize: 11, opacity: 0.7, marginBottom: 8 },
  countdown:     { fontSize: 40, fontFamily: "'Syne', sans-serif", fontWeight: 800, letterSpacing: -1, lineHeight: 1 },
  countdownLabel:{ fontSize: 12, opacity: 0.7, marginTop: 4, marginBottom: 14 },
  progressBg:    { height: 5, background: "rgba(255,255,255,.2)", borderRadius: 3, overflow: "hidden" },
  progressFill:  { height: "100%", background: "#FFD600", borderRadius: 3, transition: "width 0.6s ease" },
  wsWarning:     { background: "#FFF8E1", borderBottom: "1px solid #FFE082", padding: "8px 16px", fontSize: 12, color: "#E65100" },
  steps:         { padding: "20px 20px 0" },
  step:          { display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 20, position: "relative" },
  stepDot:       { width: 26, height: 26, borderRadius: "50%", border: "2px solid", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "white", flexShrink: 0, transition: "all .3s" },
  stepLine:      { position: "absolute", left: 12, top: 28, width: 2, height: 24, transition: "background .3s" } as any,
  stepContent:   { flex: 1, paddingTop: 3 },
  stepLabel:     { fontSize: 13, color: "#111" },
  stepActive:    { fontSize: 11, color: "#0057FF", marginTop: 2 },
  reviewBanner:  { margin: 16, background: "linear-gradient(135deg,#0057FF,#003DC7)", borderRadius: 14, padding: "18px 16px", color: "white" },
  reviewBtn:     { marginTop: 10, background: "#FFD600", color: "#111", border: "none", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 700, cursor: "pointer", width: "100%" },
  error:         { padding: 20, color: "#FF3D00", textAlign: "center" },
  loading:       { padding: 40, textAlign: "center", color: "#888" },
};
