/**
 * 세팡 고객 앱 — 실제 API 연동 버전
 * 인증: 휴대폰 OTP (NAVER SENS)
 * 배포: Next.js PWA / Capacitor
 */
import { useState, useEffect, useCallback, createContext, useContext } from "react";
import { authApi, orderApi, reviewApi, geocodeApi, pointsApi, paymentApi, tokenStore, createOrderTrackingSocket } from "@sepang/shared/lib/api-client";

// ─── Router ───────────────────────────────────────────────────────────────────
const RouterCtx = createContext({});
const useRouter = () => useContext(RouterCtx);
function Router({ children }) {
  const [path, setPath] = useState(tokenStore.get() ? "/home" : "/login");
  const [params, setParams] = useState({});
  const navigate = useCallback((to, p = {}) => { setPath(to); setParams(p); }, []);
  return (
    <RouterCtx.Provider value={{ path, params, navigate }}>
      {children}
    </RouterCtx.Provider>
  );
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
const AuthCtx = createContext({});
const useAuth = () => useContext(AuthCtx);
function AuthProvider({ children }) {
  const { navigate } = useRouter();
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!tokenStore.get()) { setIsLoading(false); return; }
    authApi.me().then(setUser).catch(() => tokenStore.clear()).finally(() => setIsLoading(false));
  }, []);

  const loginWithTokens = useCallback(async (tokens) => {
    tokenStore.set(tokens.access_token, tokens.refresh_token);
    const me = await authApi.me();
    setUser(me);
    navigate("/home");
  }, [navigate]);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    navigate("/login");
  }, [navigate]);

  return (
    <AuthCtx.Provider value={{ user, isLoading, loginWithTokens, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

// ─── Web Push 구독 ─────────────────────────────────────────────────────────────
async function subscribePush() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  try {
    const reg = await navigator.serviceWorker.ready;
    const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
    if (!vapidKey) return;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: vapidKey,
    });
    const { endpoint, keys } = sub.toJSON();
    await fetch("/api/v1/users/me/push-subscription", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${tokenStore.get()}` },
      body: JSON.stringify({ endpoint, p256dh_key: keys.p256dh, auth_key: keys.auth }),
    });
  } catch {
    // 권한 거부 시 무시
  }
}

// ─── Countdown from ISO datetime ──────────────────────────────────────────────
function useCountdown(deadlineIso) {
  const calc = () => {
    if (!deadlineIso) return "00:00:00";
    const diff = Math.max(0, new Date(deadlineIso) - Date.now());
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    return [h, m, s].map(n => String(n).padStart(2, "0")).join(":");
  };
  const [t, setT] = useState(calc);
  useEffect(() => {
    const iv = setInterval(() => setT(calc()), 1000);
    return () => clearInterval(iv);
  }, [deadlineIso]);
  return t;
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function Toast({ msg, onHide }) {
  useEffect(() => { const t = setTimeout(onHide, 2200); return () => clearTimeout(t); }, [onHide]);
  return (
    <div style={{
      position: "fixed", bottom: 80, left: "50%", transform: "translateX(-50%)",
      background: "#111", color: "white", borderRadius: 100, padding: "10px 22px",
      fontSize: 13, fontWeight: 600, zIndex: 9999, whiteSpace: "nowrap",
      boxShadow: "0 4px 20px rgba(0,0,0,.3)",
    }}>{msg}</div>
  );
}

// ─── CSS ──────────────────────────────────────────────────────────────────────
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&family=Syne:wght@700;800&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --blue: #0057FF; --blue-dark: #003DC7; --blue-light: #EEF3FF;
    --yellow: #FFD600; --green: #00C853; --red: #FF3D00;
    --muted: #888; --border: #EBEBEB; --surface: #F5F7FA; --white: #fff;
    --font-d: 'Syne', sans-serif; --font-b: 'Noto Sans KR', sans-serif;
  }
  html, body, #root { height: 100%; font-family: var(--font-b); background: var(--surface); -webkit-font-smoothing: antialiased; }
  button { font-family: var(--font-b); cursor: pointer; border: none; }
  input, textarea { font-family: var(--font-b); }
  ::-webkit-scrollbar { width: 0; }
  @keyframes pulse { 0%,100%{box-shadow:0 0 0 0 rgba(0,87,255,.4)} 50%{box-shadow:0 0 0 8px rgba(0,87,255,0)} }
  @keyframes fadeUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
  .fu { animation: fadeUp .3s ease both; }
  .app-root { max-width: 430px; margin: 0 auto; min-height: 100vh; background: var(--white); display: flex; flex-direction: column; box-shadow: 0 0 60px rgba(0,0,0,.1); }
  .status-bar { background: var(--blue-dark); padding: 10px 20px 6px; display: flex; justify-content: space-between; font-size: 11px; color: white; font-weight: 600; }
  .screen { flex: 1; overflow-y: auto; padding-bottom: 70px; background: var(--surface); }
  .bottom-nav { position: fixed; bottom: 0; left: 50%; transform: translateX(-50%); width: 100%; max-width: 430px; background: var(--white); border-top: 1px solid var(--border); display: flex; height: 66px; box-shadow: 0 -4px 20px rgba(0,0,0,.06); z-index: 100; }
  .bnav-item { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; cursor: pointer; font-size: 10px; color: var(--muted); transition: color .15s; font-weight: 500; }
  .bnav-item.active { color: var(--blue); }
  .bnav-icon { font-size: 22px; line-height: 1; }
  .app-header { background: linear-gradient(145deg,#0057FF 0%,#003DC7 100%); padding: 16px 20px 24px; color: white; position: relative; overflow: hidden; }
  .app-header::after { content: ''; position: absolute; width: 240px; height: 240px; border-radius: 50%; background: rgba(255,255,255,.05); bottom: -110px; right: -60px; }
  .header-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .app-logo { font-family: var(--font-d); font-size: 24px; font-weight: 800; }
  .app-logo span { color: var(--yellow); }
  .header-icon-btn { width: 36px; height: 36px; border-radius: 50%; background: rgba(255,255,255,.15); display: flex; align-items: center; justify-content: center; font-size: 18px; cursor: pointer; border: none; color: white; }
  .section { padding: 16px; }
  .card { background: var(--white); border-radius: 16px; box-shadow: 0 2px 8px rgba(0,0,0,.06); padding: 16px; }
  .card-title { font-size: 14px; font-weight: 700; margin-bottom: 12px; }
  .svc-card { background: var(--white); border-radius: 16px; padding: 16px; display: flex; align-items: center; gap: 13px; border: 2.5px solid transparent; cursor: pointer; transition: all .2s; box-shadow: 0 2px 8px rgba(0,0,0,.06); margin-bottom: 10px; }
  .svc-card.sel { border-color: var(--blue); background: var(--blue-light); }
  .svc-icon { width: 52px; height: 52px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 24px; flex-shrink: 0; }
  .svc-badge { background: var(--blue); color: white; border-radius: 9px; padding: 4px 10px; font-size: 11px; font-weight: 700; white-space: nowrap; flex-shrink: 0; }
  .btn-primary { width: 100%; background: var(--blue); color: white; border-radius: 16px; padding: 16px; font-size: 15px; font-weight: 700; border: none; cursor: pointer; box-shadow: 0 6px 24px rgba(0,87,255,.25); }
  .btn-primary:disabled { opacity: .5; cursor: not-allowed; }
  .badge { display: inline-flex; align-items: center; gap: 3px; padding: 3px 9px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .b-blue { background: var(--blue-light); color: var(--blue); }
  .b-green { background: #E8F5E9; color: #2E7D32; }
  .b-yellow { background: #FFF8E1; color: #B07800; }
  .b-purple { background: #F3E5F5; color: #7B1FA2; }
  .b-red { background: #FFF0ED; color: var(--red); }
  .input { width: 100%; padding: 13px 15px; border: 1.5px solid var(--border); border-radius: 10px; font-size: 14px; outline: none; transition: border .15s; }
  .input:focus { border-color: var(--blue); }
  .countdown { font-family: var(--font-d); font-size: 40px; font-weight: 800; color: var(--yellow); letter-spacing: -1px; line-height: 1; }
  .divider { height: 8px; background: var(--surface); }
  .list-item { display: flex; align-items: center; gap: 12px; padding: 14px 16px; background: var(--white); border-bottom: 1px solid var(--border); cursor: pointer; }
  .step { display: flex; gap: 14px; padding: 10px 0; position: relative; }
  .step:not(:last-child)::after { content: ''; position: absolute; left: 13px; top: 38px; width: 2px; height: calc(100% - 20px); background: var(--border); }
  .step.done::after { background: var(--blue); }
  .step-dot { width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0; z-index: 1; border: 2px solid var(--border); background: var(--white); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }
  .step.done .step-dot { background: var(--blue); border-color: var(--blue); color: white; }
  .step.active .step-dot { border-color: var(--blue); animation: pulse 1.5s infinite; }
  .login-wrap { min-height: 100vh; background: linear-gradient(160deg,#0057FF 0%,#003DC7 40%,#0D0D30 100%); padding: 60px 28px 32px; display: flex; flex-direction: column; }
  .login-box { background: white; border-radius: 22px; padding: 28px; }
  .error-msg { color: var(--red); font-size: 12px; margin-top: 8px; }
`;

// ─── Components ───────────────────────────────────────────────────────────────
function StatusBar() {
  const [time, setTime] = useState(() => {
    const n = new Date(); return `${n.getHours()}:${String(n.getMinutes()).padStart(2, "0")}`;
  });
  useEffect(() => {
    const iv = setInterval(() => {
      const n = new Date(); setTime(`${n.getHours()}:${String(n.getMinutes()).padStart(2, "0")}`);
    }, 10000);
    return () => clearInterval(iv);
  }, []);
  return <div className="status-bar"><span>{time}</span><span>📶 🔋</span></div>;
}

function BottomNav({ active }) {
  const { navigate } = useRouter();
  return (
    <div className="bottom-nav">
      {[["🏠", "홈", "/home"], ["📦", "내주문", "/orders"], ["🎁", "혜택", "/points"], ["👤", "마이", "/mypage"]].map(([icon, label, to], i) => (
        <div key={i} className={`bnav-item ${active === i ? "active" : ""}`} onClick={() => navigate(to)}>
          <span className="bnav-icon">{icon}</span><span>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Screens ──────────────────────────────────────────────────────────────────
function LoginScreen() {
  const { loginWithTokens } = useAuth();
  const [step, setStep] = useState(0);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  const handleSendOtp = async () => {
    setError(null);
    setLoading(true);
    try {
      await authApi.sendOtp(phone.replace(/-/g, ""));
      setStep(1);
      setToast("인증번호가 발송되었습니다");
    } catch (e) {
      setError(e.message || "SMS 발송 실패");
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    setError(null);
    setLoading(true);
    try {
      const tokens = await authApi.verifyOtp(phone.replace(/-/g, ""), code);
      await loginWithTokens(tokens);
      // 로그인 성공 후 Push 구독 요청
      subscribePush();
    } catch (e) {
      setError(e.message || "인증 실패");
    } finally {
      setLoading(false);
    }
  };

  return (
    <><style>{CSS}</style>
      <div className="login-wrap">
        <div style={{ fontFamily: "var(--font-d)", fontSize: 42, fontWeight: 800, color: "white", marginBottom: 8 }}>
          세<span style={{ color: "var(--yellow)" }}>팡</span>
        </div>
        <div style={{ fontSize: 14, color: "rgba(255,255,255,.6)", marginBottom: 48 }}>12시간 이내 수거·세탁·배송 완료</div>
        <div className="login-box">
          <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 20 }}>
            {step === 0 ? "휴대폰으로 시작하기" : "인증번호 입력"}
          </div>
          {step === 0 ? (
            <input className="input" style={{ marginBottom: 4 }} placeholder="010-0000-0000"
              value={phone} onChange={e => setPhone(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSendOtp()} />
          ) : (
            <input className="input" style={{ marginBottom: 4 }} placeholder="인증번호 6자리"
              value={code} onChange={e => setCode(e.target.value)} maxLength={6}
              onKeyDown={e => e.key === "Enter" && handleVerify()} />
          )}
          {error && <div className="error-msg">{error}</div>}
          <button className="btn-primary" style={{ marginTop: 14 }}
            disabled={loading || (step === 0 ? phone.length < 10 : code.length < 4)}
            onClick={step === 0 ? handleSendOtp : handleVerify}>
            {loading ? "처리 중..." : step === 0 ? "인증번호 받기" : "로그인"}
          </button>
          {step === 1 && (
            <button onClick={() => { setStep(0); setCode(""); setError(null); }}
              style={{ width: "100%", marginTop: 8, background: "transparent", border: "none", color: "var(--blue)", fontSize: 13, fontWeight: 700, padding: 8, cursor: "pointer" }}>
              다시 받기
            </button>
          )}
          <div style={{ marginTop: 16, fontSize: 11, color: "#aaa", textAlign: "center" }}>
            가입하면 서비스 이용약관 및 개인정보처리방침에 동의합니다
          </div>
        </div>
        {toast && <Toast msg={toast} onHide={() => setToast(null)} />}
      </div>
    </>
  );
}

const WASH_CATS = [
  { key: "CLOTHES_30L", icon: "🧺", label: "생활빨래 30L", price: 13000 },
  { key: "CLOTHES_50L", icon: "🧺", label: "생활빨래 50L", price: 18000 },
  { key: "BLANKET",     icon: "🛏",  label: "이불",         price: 16000 },
  { key: "SHOES",       icon: "👟", label: "운동화",       price: 10000 },
];

function HomeScreen() {
  const { user } = useAuth();
  const { navigate } = useRouter();
  const [sel, setSel] = useState("DAY");
  const [catIdx, setCatIdx] = useState(0);
  const [address, setAddress] = useState(user?.address || "");
  const [coords, setCoords] = useState(null);      // { lat, lng, address }
  const [geocoding, setGeocoding] = useState(false);
  const [geocodeError, setGeocodeError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);

  // 주소 변경 시 coords 초기화
  const handleAddressChange = (val) => {
    setAddress(val);
    setCoords(null);
    setGeocodeError(null);
  };

  const handleGeocode = async () => {
    if (!address.trim()) { setGeocodeError("주소를 입력해 주세요"); return; }
    setGeocoding(true);
    setGeocodeError(null);
    try {
      const result = await geocodeApi.search(address);
      setCoords(result);
      setAddress(result.address);
    } catch (e) {
      setGeocodeError(e.message || "주소를 찾을 수 없습니다");
    } finally {
      setGeocoding(false);
    }
  };

  const cat = WASH_CATS[catIdx];

  const handleOrder = async () => {
    if (!address) { setError("수거 주소를 입력해 주세요"); return; }
    if (!coords) { setError("주소 확인 버튼을 눌러 주소를 확인해 주세요"); return; }
    setError(null);
    setLoading(true);
    try {
      const result = await orderApi.create({
        service_type:     sel,
        wash_category:    cat.key,
        pickup_address:   coords.address,
        pickup_lat:       coords.lat,
        pickup_lng:       coords.lng,
        delivery_address: coords.address,
        delivery_lat:     coords.lat,
        delivery_lng:     coords.lng,
      });
      // 주문 생성 후 결제 화면으로 이동
      navigate("/payment", { orderId: result.order_id, totalAmount: result.total_amount, deadlineAt: result.deadline_at });
    } catch (e) {
      setError(e.message || "주문 실패. 다시 시도해 주세요.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <><style>{CSS}</style>
      <div className="app-root fu">
        <StatusBar />
        <div className="screen">
          <div className="app-header">
            <div className="header-top">
              <div className="app-logo">세<span>팡</span></div>
              <button className="header-icon-btn" onClick={() => navigate("/orders")}>🔔</button>
            </div>
            <div style={{ fontSize: 19, fontWeight: 700, marginBottom: 4 }}>
              안녕하세요, {user?.name || "고객"}님 👋
            </div>
            <div style={{ fontSize: 12, opacity: .75 }}>오늘도 12시간 안에 깔끔하게 완료해 드릴게요</div>
          </div>

          <div className="section">
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10, color: "#444" }}>수거 주소</div>
            <div style={{ display: "flex", gap: 8 }}>
              <input className="input" placeholder="수거할 주소를 입력하세요" style={{ flex: 1 }}
                value={address} onChange={e => handleAddressChange(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleGeocode()} />
              <button onClick={handleGeocode} disabled={geocoding || !address.trim()}
                style={{ flexShrink: 0, padding: "0 14px", background: coords ? "var(--green)" : "var(--blue)", color: "white", borderRadius: 10, border: "none", fontWeight: 700, fontSize: 13, cursor: "pointer", opacity: geocoding ? .6 : 1 }}>
                {geocoding ? "검색중" : coords ? "✓" : "확인"}
              </button>
            </div>
            {geocodeError && <div className="error-msg">{geocodeError}</div>}
            {coords && <div style={{ fontSize: 11, color: "var(--green)", marginTop: 4 }}>📍 {coords.address}</div>}
          </div>

          <div className="section" style={{ paddingTop: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10, color: "#444" }}>서비스 선택</div>
            {[
              { key: "DAY",   icon: "☀️", bg: "#FFF8E1", title: "당일 수령",      sub: "오전 9시 수거 → 오후 배송",  badge: "오늘 오후 7시" },
              { key: "NIGHT", icon: "🌙", bg: "#EDE7F6", title: "새벽 수령",      sub: "오후 9시 수거 → 새벽 배송",  badge: "내일 오전 7시" },
            ].map(s => (
              <div key={s.key} className={`svc-card ${sel === s.key ? "sel" : ""}`} onClick={() => setSel(s.key)}>
                <div className="svc-icon" style={{ background: s.bg }}>{s.icon}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 700 }}>{s.title}</div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{s.sub}</div>
                </div>
                <div className="svc-badge">{s.badge}</div>
              </div>
            ))}
          </div>

          <div className="section" style={{ paddingTop: 0 }}>
            <div className="card">
              <div className="card-title">세탁물 종류</div>
              <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
                {WASH_CATS.map((c, i) => (
                  <div key={i} onClick={() => setCatIdx(i)} style={{
                    flex: "1 1 40%", background: catIdx === i ? "var(--blue-light)" : "var(--surface)",
                    borderRadius: 10, padding: "10px 6px", textAlign: "center", fontSize: 11, fontWeight: 600,
                    color: catIdx === i ? "var(--blue)" : "var(--muted)", cursor: "pointer",
                    border: `1.5px solid ${catIdx === i ? "var(--blue)" : "transparent"}`,
                  }}>
                    <div style={{ fontSize: 20, marginBottom: 4 }}>{c.icon}</div>{c.label}
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                <span style={{ color: "var(--muted)" }}>예상 금액</span>
                <span style={{ fontFamily: "var(--font-d)", fontSize: 18, fontWeight: 800, color: "var(--blue)" }}>
                  {cat.price.toLocaleString()}원
                </span>
              </div>
            </div>
          </div>

          {error && <div style={{ padding: "0 16px", color: "var(--red)", fontSize: 13 }}>{error}</div>}
          <div className="section" style={{ paddingTop: 0 }}>
            <button className="btn-primary" disabled={loading} onClick={handleOrder}>
              {loading ? "주문 접수 중..." : "🚀 지금 바로 주문하기"}
            </button>
          </div>

          <div style={{ margin: "0 16px 20px", background: "linear-gradient(135deg,#FFD600,#FFA000)", borderRadius: 14, padding: "14px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#5D3B00" }}>신규 가입 혜택</div>
              <div style={{ fontSize: 16, fontWeight: 900, color: "#3D2600", marginTop: 2 }}>첫 주문 3,000원 할인</div>
            </div>
            <div style={{ fontSize: 32 }}>🎁</div>
          </div>
        </div>
        <BottomNav active={0} />
        {toast && <Toast msg={toast} onHide={() => setToast(null)} />}
      </div>
    </>
  );
}

const STATUS_STEPS = [
  { key: "PENDING",         label: "주문 접수" },
  { key: "ACCEPTED",        label: "점주 수락" },
  { key: "PICKUP_EN_ROUTE", label: "수거 이동중" },
  { key: "PICKED_UP",       label: "수거 완료" },
  { key: "WASHING",         label: "세탁 / 건조" },
  { key: "DRYING",          label: "건조" },
  { key: "DELIVERING",      label: "배송 중" },
  { key: "COMPLETED",       label: "배송 완료" },
];

function TrackingScreen() {
  const { navigate, params } = useRouter();
  const [order, setOrder] = useState(null);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const cd = useCountdown(order?.deadline_at);

  useEffect(() => {
    const orderId = params?.orderId;
    if (!orderId) { navigate("/orders"); return; }

    orderApi.get(orderId)
      .then(o => { setOrder(o); setStatus(o.status); })
      .catch(() => setError("주문 정보를 불러올 수 없습니다"));

    const ws = createOrderTrackingSocket(orderId, {
      onStatus: (s) => setStatus(s),
    });
    return () => ws.close();
  }, [params?.orderId]);

  if (error) return (
    <><style>{CSS}</style>
      <div className="app-root fu" style={{ justifyContent: "center", alignItems: "center", gap: 16 }}>
        <div style={{ fontSize: 36 }}>😢</div>
        <div style={{ color: "var(--muted)", fontSize: 14 }}>{error}</div>
        <button className="btn-primary" style={{ width: "auto", padding: "12px 28px" }} onClick={() => navigate("/orders")}>
          주문 목록으로
        </button>
      </div>
    </>
  );

  if (!order) return (
    <><style>{CSS}</style>
      <div className="app-root" style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ color: "var(--muted)", fontSize: 14 }}>로딩 중...</div>
      </div>
    </>
  );

  const currentIdx = STATUS_STEPS.findIndex(s => s.key === (status || order.status));
  const isUrgent = order.deadline_at && (new Date(order.deadline_at) - Date.now()) < 2 * 3600 * 1000;

  return (
    <><style>{CSS}</style>
      <div className="app-root fu">
        <StatusBar />
        <div className="screen">
          <div className="app-header" style={{ paddingBottom: 20 }}>
            <div className="header-top">
              <button className="header-icon-btn" onClick={() => navigate("/orders")}>←</button>
              <div style={{ fontSize: 14, fontWeight: 700 }}>실시간 추적</div>
              <div style={{ width: 36 }} />
            </div>
            <div style={{ fontSize: 11, opacity: .7, marginBottom: 6 }}>
              주문 #{order.id.slice(-6).toUpperCase()}
            </div>
            <div className="countdown" style={{ color: isUrgent ? "var(--red)" : "var(--yellow)" }}>{cd}</div>
            <div style={{ fontSize: 12, opacity: .7, marginTop: 4 }}>배송 완료까지 남은 시간</div>
          </div>

          <div style={{ padding: "14px 16px 0" }}>
            <div style={{ background: "var(--border)", borderRadius: 4, height: 6, overflow: "hidden", marginBottom: 5 }}>
              <div style={{ width: `${Math.round((currentIdx / (STATUS_STEPS.length - 1)) * 100)}%`, height: "100%", background: "var(--blue)", borderRadius: 4, transition: "width .5s" }} />
            </div>

            <div className="card" style={{ marginTop: 14, marginBottom: 12 }}>
              {STATUS_STEPS.filter(s => !["DRYING"].includes(s.key)).map((s, i) => {
                const sIdx = STATUS_STEPS.findIndex(x => x.key === s.key);
                const done = sIdx < currentIdx;
                const active = sIdx === currentIdx;
                return (
                  <div key={s.key} className={`step ${done ? "done" : ""} ${active ? "active" : ""}`}>
                    <div className="step-dot">{done ? "✓" : active ? "⟳" : ""}</div>
                    <div style={{ flex: 1, paddingTop: 2 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{s.label}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>수거 주소</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{order.pickup_address}</div>
              <div style={{ borderTop: "1px solid var(--border)", margin: "12px 0" }} />
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>배송 주소</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{order.delivery_address}</div>
            </div>

            {order.status === "COMPLETED" && (
              <button className="btn-primary" style={{ marginBottom: 16 }}
                onClick={() => navigate("/review", { orderId: order.id })}>
                ⭐ 리뷰 작성하기
              </button>
            )}
          </div>
        </div>
        <BottomNav active={1} />
      </div>
    </>
  );
}

const STATUS_META = {
  PENDING:         { label: "접수", cls: "b-yellow" },
  ACCEPTED:        { label: "수락됨", cls: "b-blue" },
  PICKUP_EN_ROUTE: { label: "수거중", cls: "b-blue" },
  PICKED_UP:       { label: "수거완료", cls: "b-blue" },
  WASHING:         { label: "세탁중", cls: "b-purple" },
  DRYING:          { label: "건조중", cls: "b-purple" },
  DELIVERING:      { label: "배송중", cls: "b-blue" },
  COMPLETED:       { label: "완료", cls: "b-green" },
  CANCELLED:       { label: "취소", cls: "b-red" },
};

function OrdersScreen() {
  const { navigate } = useRouter();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    orderApi.list()
      .then(setOrders)
      .catch(() => setError("주문 목록을 불러올 수 없습니다"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <><style>{CSS}</style>
      <div className="app-root fu">
        <StatusBar />
        <div className="screen">
          <div style={{ padding: "16px 16px 8px", background: "white", borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontFamily: "var(--font-d)", fontSize: 20, fontWeight: 800 }}>내 주문</div>
          </div>
          {loading && <div style={{ padding: 32, textAlign: "center", color: "var(--muted)" }}>로딩 중...</div>}
          {error && <div style={{ padding: 32, textAlign: "center", color: "var(--red)" }}>{error}</div>}
          {!loading && orders.length === 0 && (
            <div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>
              <div style={{ fontSize: 36, marginBottom: 12 }}>📭</div>
              <div>아직 주문 내역이 없어요</div>
            </div>
          )}
          {orders.map((o) => {
            const s = STATUS_META[o.status] || {};
            const active = !["COMPLETED", "CANCELLED"].includes(o.status);
            return (
              <div key={o.id} onClick={() => active && navigate("/tracking", { orderId: o.id })}
                style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", background: "white", borderBottom: "1px solid #F5F5F5", cursor: active ? "pointer" : "default" }}>
                <div style={{ width: 44, height: 44, borderRadius: 12, background: o.service_type === "NIGHT" ? "#EDE7F6" : "#FFF8E1", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, flexShrink: 0 }}>
                  {o.service_type === "NIGHT" ? "🌙" : "☀️"}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--muted)" }}>
                      #{o.id.slice(-6).toUpperCase()}
                    </span>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>
                      {new Date(o.ordered_at).toLocaleDateString("ko-KR", { month: "2-digit", day: "2-digit" })}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className={`badge ${s.cls}`}>{s.label}</span>
                    <span style={{ fontFamily: "var(--font-d)", fontWeight: 700, fontSize: 14 }}>
                      {o.total_amount.toLocaleString()}원
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <BottomNav active={1} />
      </div>
    </>
  );
}

function PointsScreen() {
  const [data, setData] = useState(null);
  const [coupons, setCoupons] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([pointsApi.get(), pointsApi.coupons()])
      .then(([p, c]) => { setData(p); setCoupons(c.coupons); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const balance = data?.balance ?? 0;
  const history = data?.history ?? [];

  return (
    <><style>{CSS}</style>
      <div className="app-root fu">
        <StatusBar />
        <div className="screen">
          <div style={{ padding: "16px 16px 8px", background: "white", borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontFamily: "var(--font-d)", fontSize: 20, fontWeight: 800 }}>포인트 / 혜택</div>
          </div>

          <div style={{ margin: 16, background: "linear-gradient(135deg,#0057FF,#003DC7)", borderRadius: 22, padding: 22, color: "white" }}>
            <div style={{ fontSize: 12, opacity: .75, marginBottom: 6 }}>보유 포인트</div>
            <div style={{ fontFamily: "var(--font-d)", fontSize: 36, fontWeight: 800 }}>
              {loading ? "..." : balance.toLocaleString()}P
            </div>
            <div style={{ fontSize: 12, opacity: .65, marginTop: 4 }}>주문 시 현금처럼 사용 가능</div>
          </div>

          <div className="section">
            <div className="card">
              <div className="card-title">🎫 보유 쿠폰 {coupons.length}장</div>
              {coupons.length === 0 ? (
                <div style={{ padding: "12px 0", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
                  보유 쿠폰이 없습니다
                </div>
              ) : coupons.map((c, i) => (
                <div key={c.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderBottom: i < coupons.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{c.name}</div>
                    {c.expires_at && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>~ {c.expires_at.slice(0, 10)}까지</div>}
                  </div>
                  <span style={{ fontFamily: "var(--font-d)", fontWeight: 800, fontSize: 16, color: "var(--red)" }}>
                    {c.discount_amount ? `-${c.discount_amount.toLocaleString()}원` : c.discount_rate ? `-${c.discount_rate}%` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {history.length > 0 && (
            <div className="section" style={{ paddingTop: 0 }}>
              <div className="card">
                <div className="card-title">포인트 내역</div>
                {history.slice(0, 10).map((h, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "10px 0", borderBottom: i < Math.min(history.length, 10) - 1 ? "1px solid var(--border)" : "none" }}>
                    <div style={{ fontSize: 13 }}>{h.reason}</div>
                    <span style={{ fontFamily: "var(--font-d)", fontWeight: 700, color: h.amount > 0 ? "var(--blue)" : "var(--muted)" }}>
                      {h.amount > 0 ? "+" : ""}{h.amount.toLocaleString()}P
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <BottomNav active={2} />
      </div>
    </>
  );
}

function ReviewScreen() {
  const { navigate, params } = useRouter();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  const orderId = params?.orderId;

  const handleSubmit = async () => {
    if (rating === 0) { setError("별점을 선택해 주세요"); return; }
    setError(null);
    setLoading(true);
    try {
      await reviewApi.create(orderId, rating, comment || undefined);
      setDone(true);
      setTimeout(() => navigate("/orders"), 1500);
    } catch (e) {
      setError(e.message || "리뷰 등록에 실패했습니다");
    } finally {
      setLoading(false);
    }
  };

  if (done) return (
    <><style>{CSS}</style>
      <div className="app-root" style={{ justifyContent: "center", alignItems: "center", gap: 16 }}>
        <div style={{ fontSize: 52 }}>⭐</div>
        <div style={{ fontSize: 17, fontWeight: 700 }}>리뷰가 등록되었습니다!</div>
        <div style={{ fontSize: 13, color: "var(--muted)" }}>100 포인트가 적립될 예정이에요</div>
      </div>
    </>
  );

  return (
    <><style>{CSS}</style>
      <div className="app-root fu">
        <StatusBar />
        <div className="screen">
          <div style={{ padding: "16px 16px 8px", background: "white", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12 }}>
            <button onClick={() => navigate("/orders")} style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer" }}>←</button>
            <div style={{ fontFamily: "var(--font-d)", fontSize: 18, fontWeight: 800 }}>리뷰 작성</div>
          </div>

          <div style={{ padding: 20 }}>
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16, textAlign: "center" }}>
                세탁 서비스는 어떠셨나요?
              </div>
              <div style={{ display: "flex", justifyContent: "center", gap: 8, marginBottom: 8 }}>
                {[1, 2, 3, 4, 5].map(n => (
                  <button key={n} onClick={() => setRating(n)}
                    style={{ fontSize: 36, background: "none", border: "none", cursor: "pointer", opacity: n <= rating ? 1 : .3, transition: "opacity .15s" }}>
                    ⭐
                  </button>
                ))}
              </div>
              <div style={{ textAlign: "center", fontSize: 13, color: "var(--muted)", height: 20 }}>
                {["", "별로예요", "그냥 그래요", "보통이에요", "좋았어요", "최고예요!"][rating]}
              </div>
            </div>

            <div className="card">
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>상세 리뷰 (선택)</div>
              <textarea className="input" placeholder="세탁 품질, 배송, 포장 등 자유롭게 남겨주세요"
                style={{ height: 120, resize: "none", lineHeight: 1.6 }}
                value={comment} onChange={e => setComment(e.target.value)} maxLength={500} />
              <div style={{ fontSize: 11, color: "var(--muted)", textAlign: "right", marginTop: 4 }}>
                {comment.length}/500
              </div>
            </div>

            {error && <div className="error-msg" style={{ marginTop: 12 }}>{error}</div>}

            <button className="btn-primary" style={{ marginTop: 20 }}
              disabled={loading || rating === 0} onClick={handleSubmit}>
              {loading ? "등록 중..." : "리뷰 등록하기 (+100P)"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

function MyPageScreen() {
  const { user, logout } = useAuth();
  const { navigate } = useRouter();
  const menus = [
    ["📍", "배송지 관리", user?.address || "미설정"],
    ["🔔", "알림 설정", "ON"],
    ["⭐", "리뷰 관리", ""],
    ["📞", "고객센터", "1:1 문의"],
  ];
  return (
    <><style>{CSS}</style>
      <div className="app-root fu">
        <StatusBar />
        <div className="screen">
          <div style={{ background: "white", padding: "24px 16px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ width: 60, height: 60, borderRadius: "50%", background: "linear-gradient(135deg,var(--blue),var(--blue-dark))", display: "flex", alignItems: "center", justifyContent: "center", color: "white", fontSize: 24, fontWeight: 700 }}>
                {user?.name?.charAt(0) || "?"}
              </div>
              <div>
                <div style={{ fontFamily: "var(--font-d)", fontSize: 18, fontWeight: 800 }}>{user?.name}</div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{user?.phone}</div>
              </div>
            </div>
          </div>
          <div className="divider" />
          {menus.map(([icon, label, sub], i) => (
            <div key={i} className="list-item">
              <span style={{ fontSize: 20, width: 28, textAlign: "center" }}>{icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{label}</div>
                {sub && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 1 }}>{sub}</div>}
              </div>
              <span style={{ color: "var(--muted)", fontSize: 18 }}>›</span>
            </div>
          ))}
          <div className="divider" />
          <div style={{ padding: "16px 16px 32px", background: "white" }}>
            <button onClick={logout} style={{ width: "100%", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 14, fontSize: 14, fontWeight: 700, color: "var(--muted)", cursor: "pointer" }}>
              로그아웃
            </button>
          </div>
        </div>
        <BottomNav active={3} />
      </div>
    </>
  );
}

function LoadingScreen() {
  return (
    <><style>{CSS}</style>
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#0057FF" }}>
        <div style={{ fontFamily: "var(--font-d)", fontSize: 42, fontWeight: 800, color: "white" }}>
          세<span style={{ color: "#FFD600" }}>팡</span>
        </div>
      </div>
    </>
  );
}

// ─── 결제 화면 ────────────────────────────────────────────────────────────────
function PaymentScreen() {
  const { navigate, params } = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [payInfo, setPayInfo] = useState(null);

  useEffect(() => {
    if (!params?.orderId) { navigate("/home"); return; }
    paymentApi.prepare(params.orderId)
      .then(info => { setPayInfo(info); setLoading(false); })
      .catch(e => { setError(e.message || "결제 준비에 실패했습니다"); setLoading(false); });
  }, [params?.orderId]);

  const handlePay = async () => {
    if (!payInfo) return;
    setLoading(true);
    try {
      // 토스페이먼츠 SDK 동적 로드
      const { loadTossPayments } = await import("@tosspayments/payment-sdk");
      const toss = await loadTossPayments(payInfo.client_key);
      await toss.requestPayment("카드", {
        amount:      payInfo.amount,
        orderId:     payInfo.order_id,
        orderName:   payInfo.order_name,
        successUrl:  `${window.location.origin}/payment/success`,
        failUrl:     `${window.location.origin}/payment/fail`,
      });
    } catch (e) {
      if (e.code !== "USER_CANCEL") setError(e.message || "결제에 실패했습니다");
      setLoading(false);
    }
  };

  const categoryLabels = { CLOTHES_30L: "세탁물 30L", CLOTHES_50L: "세탁물 50L", BLANKET: "이불", SHOES: "신발" };

  if (loading) return (
    <><style>{CSS}</style>
      <div className="app-root" style={{ justifyContent: "center", alignItems: "center" }}>
        <div style={{ color: "var(--muted)", fontSize: 14 }}>결제 준비 중...</div>
      </div>
    </>
  );

  return (
    <><style>{CSS}</style>
      <div className="app-root fu">
        <StatusBar />
        <div className="screen">
          <div className="app-header">
            <div className="header-top">
              <button className="header-icon-btn" onClick={() => navigate("/orders")}>←</button>
              <div style={{ fontSize: 14, fontWeight: 700 }}>결제</div>
              <div style={{ width: 36 }} />
            </div>
          </div>
          <div style={{ padding: "16px 16px 32px" }}>
            {error && <div style={{ background: "#FFF0F0", border: "1px solid var(--red)", borderRadius: 12, padding: 14, marginBottom: 16, fontSize: 13, color: "var(--red)" }}>{error}</div>}
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 12 }}>주문 정보</div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: 13, color: "var(--muted)" }}>서비스</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{payInfo?.order_name}</span>
              </div>
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12, display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 14, fontWeight: 700 }}>결제 금액</span>
                <span style={{ fontSize: 18, fontWeight: 800, color: "var(--blue)" }}>
                  {(payInfo?.amount || 0).toLocaleString()}원
                </span>
              </div>
            </div>
            <div className="card" style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>결제 수단</div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>신용/체크카드, 간편결제</div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>토스페이먼츠 안전 결제</div>
            </div>
            <button className="btn-primary" onClick={handlePay} disabled={loading} style={{ marginBottom: 12 }}>
              {(payInfo?.amount || 0).toLocaleString()}원 결제하기
            </button>
            <button onClick={() => navigate("/orders")}
              style={{ width: "100%", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 14, fontSize: 14, color: "var(--muted)", cursor: "pointer" }}>
              취소
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// ─── 결제 성공 화면 ────────────────────────────────────────────────────────────
function PaymentSuccessScreen() {
  const { navigate } = useRouter();
  const params = new URLSearchParams(window.location.search);
  const paymentKey = params.get("paymentKey");
  const orderId    = params.get("orderId");
  const amount     = params.get("amount");
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!paymentKey || !orderId || !amount) { setError("잘못된 결제 정보입니다"); return; }
    paymentApi.confirm(paymentKey, orderId, Number(amount))
      .then(() => setDone(true))
      .catch(e => setError(e.message || "결제 확인에 실패했습니다"));
  }, []);

  return (
    <><style>{CSS}</style>
      <div className="app-root" style={{ justifyContent: "center", alignItems: "center", textAlign: "center", padding: 24 }}>
        {!done && !error && <div style={{ color: "var(--muted)", fontSize: 14 }}>결제 확인 중...</div>}
        {done && (
          <>
            <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>결제 완료!</div>
            <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 32 }}>
              {Number(amount).toLocaleString()}원이 결제되었습니다.
            </div>
            <button className="btn-primary" onClick={() => navigate("/orders")}>주문 내역 확인</button>
          </>
        )}
        {error && (
          <>
            <div style={{ fontSize: 48, marginBottom: 16 }}>❌</div>
            <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: "var(--red)" }}>결제 오류</div>
            <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 32 }}>{error}</div>
            <button className="btn-primary" onClick={() => navigate("/orders")}>주문 내역으로</button>
          </>
        )}
      </div>
    </>
  );
}

// ─── 결제 실패 화면 ────────────────────────────────────────────────────────────
function PaymentFailScreen() {
  const { navigate } = useRouter();
  const params = new URLSearchParams(window.location.search);
  const message = params.get("message") || "결제가 취소되었거나 실패했습니다.";

  return (
    <><style>{CSS}</style>
      <div className="app-root" style={{ justifyContent: "center", alignItems: "center", textAlign: "center", padding: 24 }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>❌</div>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8, color: "var(--red)" }}>결제 실패</div>
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 32 }}>{decodeURIComponent(message)}</div>
        <button className="btn-primary" onClick={() => navigate("/orders")}>주문 내역으로</button>
      </div>
    </>
  );
}

// ─── Route Switch ─────────────────────────────────────────────────────────────
function RouteSwitch() {
  const { path } = useRouter();
  const { isLoading } = useAuth();

  if (isLoading) return <LoadingScreen />;

  const map = {
    "/login":           LoginScreen,
    "/home":            HomeScreen,
    "/payment":         PaymentScreen,
    "/payment/success": PaymentSuccessScreen,
    "/payment/fail":    PaymentFailScreen,
    "/tracking":        TrackingScreen,
    "/orders":          OrdersScreen,
    "/points":          PointsScreen,
    "/mypage":          MyPageScreen,
    "/review":          ReviewScreen,
  };
  const C = map[path] || LoginScreen;
  return <C />;
}

export default function CustomerApp() {
  return (
    <Router>
      <AuthProvider>
        <RouteSwitch />
      </AuthProvider>
    </Router>
  );
}
