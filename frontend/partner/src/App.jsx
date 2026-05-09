/**
 * ╔══════════════════════════════════════════════════════════╗
 * ║  세팡 점주 파트너 앱  |  partner.sepang.kr               ║
 * ║  배포: Next.js PWA — 점주 전용, 외부 비공개             ║
 * ║  인증: 사업자번호 + 비밀번호                             ║
 * ╚══════════════════════════════════════════════════════════╝
 */
import { useState, useEffect, createContext, useContext, useRef } from "react";
import { authApi, orderApi, settlementApi, tokenStore } from "@sepang/shared/lib/api-client";

// ─── Web Push 구독 (로그인 후 호출) ───────────────────────────────────────────
async function subscribePush() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  try {
    const reg = await navigator.serviceWorker.ready;
    const vapidKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
    if (!vapidKey) return;
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: vapidKey });
    const { endpoint, keys } = sub.toJSON();
    const token = tokenStore.get();
    if (!token) return;
    await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/users/me/push-subscription`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ endpoint, p256dh_key: keys.p256dh, auth_key: keys.auth }),
    });
  } catch {
    // 권한 거부 또는 미지원 환경에서 무시
  }
}

// ─── Router ───────────────────────────────────────────────────────────────────
const RouterCtx = createContext({});
const useRouter = () => useContext(RouterCtx);
function Router({ children }) {
  const [path, setPath] = useState("/login");
  return <RouterCtx.Provider value={{ path, navigate: setPath }}>{children}</RouterCtx.Provider>;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
const AuthCtx = createContext({});
const useAuth = () => useContext(AuthCtx);
function AuthProvider({ children }) {
  const { navigate } = useRouter();
  const [partner, setPartner] = useState(null);
  return (
    <AuthCtx.Provider value={{
      partner,
      login: (p) => setPartner(p),
      logout: () => { authApi.logout(); setPartner(null); navigate("/login"); }
    }}>
      {children}
    </AuthCtx.Provider>
  );
}

// ─── Countdown ────────────────────────────────────────────────────────────────
function useCountdown(deadlineAt) {
  const [remaining, setRemaining] = useState("");
  useEffect(() => {
    if (!deadlineAt) return;
    const update = () => {
      const diff = new Date(deadlineAt) - new Date();
      if (diff <= 0) { setRemaining("00:00:00"); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining([h, m, s].map(n => String(n).padStart(2, "0")).join(":"));
    };
    update();
    const iv = setInterval(update, 1000);
    return () => clearInterval(iv);
  }, [deadlineAt]);
  return remaining;
}

// ─── Toast ────────────────────────────────────────────────────────────────────
function Toast({ msg, onHide }) {
  useEffect(() => { const t = setTimeout(onHide, 2200); return () => clearTimeout(t); }, []);
  return (
    <div style={{ position:"fixed", bottom:80, left:"50%", transform:"translateX(-50%)", background:"#111", color:"white", borderRadius:100, padding:"10px 22px", fontSize:13, fontWeight:600, zIndex:9999, whiteSpace:"nowrap", boxShadow:"0 4px 20px rgba(0,0,0,.3)" }}>{msg}</div>
  );
}

// ─── CSS ──────────────────────────────────────────────────────────────────────
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&family=Syne:wght@700;800&display=swap');
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
  :root{
    --blue:#0057FF;--blue-l:#EEF3FF;
    --yellow:#FFD600;--yellow-d:#B07800;
    --green:#00C853;--green-l:#E8F5E9;
    --red:#FF3D00;--red-l:#FFF0ED;
    --purple:#7C4DFF;--purple-l:#F3E5F5;
    --muted:#888;--border:#E8E8E8;--surface:#F5F7FA;
    --fd:'Syne',sans-serif;--fb:'Noto Sans KR',sans-serif;
  }
  html,body,#root{height:100%;font-family:var(--fb);background:#0D0D0D;-webkit-font-smoothing:antialiased;}
  button{font-family:var(--fb);cursor:pointer;border:none;}
  input{font-family:var(--fb);}
  ::-webkit-scrollbar{width:0;}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
  @keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
  @keyframes spin{to{transform:rotate(360deg)}}
  .fu{animation:fadeUp .3s ease both;}
  .app{max-width:430px;margin:0 auto;min-height:100vh;background:var(--surface);display:flex;flex-direction:column;box-shadow:0 0 60px rgba(0,0,0,.3);}
  .screen{flex:1;overflow-y:auto;padding-bottom:68px;}
  .topbar{background:#111;padding:13px 16px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:50;}
  .t-logo{font-family:var(--fd);font-size:20px;font-weight:800;color:white;}
  .t-logo span{color:var(--yellow);}
  .t-shop{font-size:12px;color:#aaa;margin-top:1px;}
  .online-pill{display:flex;align-items:center;gap:5px;background:rgba(0,200,83,.15);border:1px solid rgba(0,200,83,.3);border-radius:20px;padding:4px 10px;font-size:11px;color:var(--green);font-weight:700;}
  .online-dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:blink 1.5s infinite;}
  .bnav{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:100%;max-width:430px;background:#111;border-top:1px solid #1e1e1e;display:flex;height:64px;z-index:50;}
  .bnav-item{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;cursor:pointer;font-size:10px;color:#444;transition:color .15s;}
  .bnav-item.active{color:var(--yellow);}
  .earn-strip{background:#111;padding:13px 15px 17px;}
  .earn-row{display:flex;gap:9px;}
  .earn-card{flex:1;background:#1a1a1a;border-radius:12px;padding:11px 12px;border:1px solid #222;}
  .earn-lbl{font-size:10px;color:#444;text-transform:uppercase;letter-spacing:.5px;margin-bottom:3px;}
  .earn-val{font-family:var(--fd);font-size:17px;font-weight:800;color:var(--yellow);}
  .earn-val.w{color:white;}
  .pool{background:white;border-radius:13px;padding:13px;border-left:4px solid var(--blue);margin-bottom:9px;box-shadow:0 2px 8px rgba(0,0,0,.06);}
  .pool.urgent{border-left-color:var(--red);}
  .pool.night{border-left-color:var(--purple);}
  .badge{display:inline-flex;align-items:center;gap:3px;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:600;}
  .b-yellow{background:#FFF8E1;color:var(--yellow-d);}
  .b-purple{background:var(--purple-l);color:var(--purple);}
  .b-red{background:var(--red-l);color:var(--red);}
  .b-dark{background:#222;color:#aaa;}
  .b-blue{background:var(--blue-l);color:var(--blue);}
  .b-green{background:var(--green-l);color:#2E7D32;}
  .accept-btn{width:100%;height:46px;background:var(--blue);color:white;border-radius:12px;font-size:14px;font-weight:700;border:none;cursor:pointer;}
  .card{background:white;border-radius:13px;padding:14px;box-shadow:0 2px 8px rgba(0,0,0,.05);}
  .card-title{font-size:13px;font-weight:700;margin-bottom:10px;}
  .cd-wrap{background:linear-gradient(135deg,#111,#1a1a2e);border-radius:13px;padding:15px;margin-bottom:11px;}
  .cd-val{font-family:var(--fd);font-size:34px;font-weight:800;color:var(--yellow);letter-spacing:-1px;}
  .step-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;}
  .step-btn{padding:15px 10px;border-radius:12px;text-align:center;font-size:13px;font-weight:700;cursor:pointer;border:2px solid transparent;}
  .step-btn.done{background:var(--blue);color:white;border-color:var(--blue);}
  .step-btn.active{background:var(--blue-l);color:var(--blue);border-color:var(--blue);}
  .step-btn.pending{background:var(--surface);color:var(--muted);border-color:var(--border);}
  .photo{background:var(--surface);border-radius:10px;border:2px dashed var(--border);height:100px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;cursor:pointer;}
  .photo.up{border-style:solid;border-color:var(--green);background:var(--green-l);}
  .settle-card{background:linear-gradient(135deg,#111,#1a1a2e);border-radius:13px;padding:17px;margin-bottom:11px;border:1px solid #222;}
  .settle-val{font-family:var(--fd);font-size:28px;font-weight:800;color:var(--yellow);}
  .data-row{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--border);font-size:13px;}
  .data-row:last-child{border-bottom:none;}
  .tabs{display:flex;background:#111;border-radius:10px;padding:3px;margin-bottom:12px;}
  .tab{flex:1;padding:7px;border:none;border-radius:8px;font-size:12px;font-weight:700;color:#444;background:transparent;cursor:pointer;}
  .tab.active{background:#222;color:var(--yellow);}
  .hist{background:white;border-radius:12px;padding:11px 13px;margin-bottom:7px;box-shadow:0 2px 6px rgba(0,0,0,.05);}
  .spinner{display:inline-block;width:20px;height:20px;border:2px solid #333;border-top-color:var(--yellow);border-radius:50%;animation:spin .6s linear infinite;}
  .error-msg{background:#1a0000;border:1px solid #3a0000;border-radius:9px;padding:9px 12px;font-size:11px;color:#FF7043;}
`;

// ─── Shared Components ────────────────────────────────────────────────────────
function TopBar() {
  const { partner } = useAuth();
  return (
    <div className="topbar">
      <div><div className="t-logo">세<span>팡</span></div><div className="t-shop">{partner?.shopName||"-"}</div></div>
      <div style={{display:"flex",alignItems:"center",gap:8}}>
        <div className="online-pill"><div className="online-dot"/>운영중</div>
      </div>
    </div>
  );
}

function BottomNav({ active }) {
  const { navigate } = useRouter();
  return (
    <div className="bnav">
      {[["📋","주문","/orders"],["⚡","작업","/task"],["📜","내역","/history"],["💰","정산","/settlement"]].map(([icon,label,to],i)=>(
        <div key={i} className={`bnav-item ${active===i?"active":""}`} onClick={()=>navigate(to)}>
          <span style={{fontSize:20}}>{icon}</span><span>{label}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Screens ──────────────────────────────────────────────────────────────────
function LoginScreen() {
  const { login } = useAuth(); const { navigate } = useRouter();
  const [id,setId]=useState(""); const [pw,setPw]=useState("");
  const [loading,setLoading]=useState(false); const [error,setError]=useState("");
  const inputStyle={width:"100%",padding:"11px 12px",border:"1.5px solid #222",borderRadius:8,fontSize:12,background:"#0a0a0a",color:"white",outline:"none",fontFamily:"inherit",marginBottom:10};

  async function handleLogin() {
    setLoading(true); setError("");
    try {
      const data = await authApi.partnerLogin(id, pw);
      tokenStore.set(data.access_token, data.refresh_token);
      const me = await authApi.me();
      login({ name: me.name, shopName: me.shop_name ?? "내 점포", shopId: data.shop_id, rating: me.rating ?? 4.9 });
      subscribePush();
      navigate("/orders");
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }

  return (
    <><style>{CSS}</style>
    <div style={{minHeight:"100vh",background:"#0D0D0D",padding:"52px 20px 28px",display:"flex",flexDirection:"column"}}>
      <div style={{fontFamily:"var(--fd)",fontSize:32,fontWeight:800,color:"white",marginBottom:4}}>세<span style={{color:"var(--yellow)"}}>팡</span></div>
      <div style={{fontSize:12,color:"#333",marginBottom:36}}>파트너 점주 전용 앱 · partner.sepang.kr</div>
      <div style={{background:"#161616",borderRadius:16,padding:20,border:"1px solid #222"}}>
        <div style={{fontSize:14,fontWeight:700,color:"white",marginBottom:14}}>점주 로그인</div>
        {error && <div className="error-msg" style={{marginBottom:10}}>{error}</div>}
        <label style={{fontSize:11,color:"#555",marginBottom:3,display:"block"}}>아이디 (사업자번호)</label>
        <input style={inputStyle} placeholder="000-00-00000" value={id} onChange={e=>setId(e.target.value)}/>
        <label style={{fontSize:11,color:"#555",marginBottom:3,display:"block"}}>비밀번호</label>
        <input style={{...inputStyle,marginBottom:16}} type="password" placeholder="••••••••" value={pw} onChange={e=>setPw(e.target.value)}/>
        <button style={{width:"100%",background:"var(--yellow)",color:"#111",borderRadius:10,padding:"13px",fontSize:14,fontWeight:900,border:"none",cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",gap:8}}
          onClick={handleLogin} disabled={loading}>
          {loading ? <span className="spinner"/> : "로그인"}
        </button>
        <div style={{marginTop:12,fontSize:11,color:"#333",textAlign:"center",lineHeight:1.8}}>파트너 가입 문의: partner@sepang.kr</div>
      </div>
    </div></>
  );
}

function OrdersScreen() {
  const { partner } = useAuth(); const { navigate } = useRouter();
  const [orders, setOrders] = useState([]);
  const [accepted, setAccepted] = useState({});
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const currentOrderRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await orderApi.nearbyOrders();
        if (!cancelled) setOrders(data);
      } catch(e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const iv = setInterval(load, 30000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  async function handleAccept(order, idx) {
    try {
      await orderApi.updateStatus(order.order_id, "ACCEPTED");
      setAccepted(a => ({...a, [idx]: true}));
      currentOrderRef.current = order;
      setToast("✅ 수락 완료!");
      setTimeout(() => navigate("/task"), 1100);
    } catch(e) {
      setToast(`❌ ${e.message}`);
    }
  }

  const urgentOrder = orders.find(o => o.hours_left < 1);

  return (
    <><style>{CSS}</style>
    <div className="app fu">
      <TopBar/>
      <div className="screen">
        <div className="earn-strip">
          <div className="earn-row">
            <div className="earn-card"><div className="earn-lbl">오늘 수입</div><div className="earn-val">-원</div></div>
            <div className="earn-card"><div className="earn-lbl">완료 건수</div><div className="earn-val w">-건</div></div>
            <div className="earn-card"><div className="earn-lbl">평점</div><div className="earn-val">⭐{partner?.rating||"-"}</div></div>
          </div>
        </div>
        {urgentOrder && (
          <div style={{margin:"11px 13px 0",background:"#1a0000",border:"1px solid #3a0000",borderRadius:11,padding:"9px 12px",fontSize:11,color:"#FF7043",display:"flex",gap:7,alignItems:"center"}}>
            ⚠️ <span><strong>{urgentOrder.pickup_address}</strong> 마감 임박 — 즉시 수락 필요</span>
          </div>
        )}
        <div style={{padding:"12px 13px 0"}}>
          <div style={{fontSize:11,color:"#666",fontWeight:700,textTransform:"uppercase",letterSpacing:".5px",marginBottom:8}}>
            📍 반경 내 신규 주문 ({orders.length}건)
          </div>
          {loading && <div style={{display:"flex",justifyContent:"center",padding:24}}><div className="spinner"/></div>}
          {error && <div className="error-msg">{error}</div>}
          {orders.map((o,i)=>(
            <div key={i} className={`pool ${o.hours_left<2?"urgent":""} ${o.service_type==="NIGHT"?"night":""}`}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:7}}>
                <div>
                  <div style={{fontSize:13,fontWeight:700}}>{o.pickup_address}</div>
                  <div style={{fontSize:11,color:"#888",marginTop:2}}>{o.wash_category} · {Math.round(o.distance_m)}m</div>
                </div>
                <div style={{fontFamily:"var(--fd)",fontSize:17,fontWeight:800,color:"var(--blue)"}}>+{o.total_amount.toLocaleString()}원</div>
              </div>
              <div style={{display:"flex",gap:5,marginBottom:10}}>
                <span className="badge b-dark">📍 {(o.distance_m/1000).toFixed(1)}km</span>
                <span className={`badge ${o.service_type==="NIGHT"?"b-purple":"b-yellow"}`}>{o.service_type}</span>
                {o.hours_left < 2 && <span className="badge b-red">⚠️ 마감임박</span>}
              </div>
              {accepted[i]
                ? <div style={{background:"#E8F5E9",borderRadius:9,padding:11,textAlign:"center",fontSize:12,color:"#2E7D32",fontWeight:700}}>✅ 수락 완료! 수거지로 이동하세요</div>
                : <button className="accept-btn" onClick={()=>handleAccept(o,i)}>➤ 주문 수락하기</button>
              }
            </div>
          ))}
          {!loading && orders.length === 0 && !error && (
            <div style={{textAlign:"center",padding:32,color:"#888",fontSize:13}}>📭 반경 내 대기 주문이 없습니다</div>
          )}
        </div>
      </div>
      <BottomNav active={0}/>
      {toast&&<Toast msg={toast} onHide={()=>setToast(null)}/>}
    </div></>
  );
}

function TaskScreen() {
  const [activeOrder, setActiveOrder] = useState(null);
  const [step, setStep] = useState(0);
  const [photos, setPhotos] = useState({pickup: false, delivery: false});
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    orderApi.list().then(orders => {
      const active = orders.find(o => ["ACCEPTED","PICKED_UP","WASHING","DRYING","DELIVERING"].includes(o.status));
      if (active) {
        setActiveOrder(active);
        const stepMap = {ACCEPTED:0,PICKED_UP:1,WASHING:2,DRYING:3,DELIVERING:3};
        setStep(stepMap[active.status] ?? 0);
      }
    }).catch(() => {});
  }, []);

  const countdown = useCountdown(activeOrder?.deadline_at);
  const STEPS = [
    {key:1,label:"수거 완료",  icon:"🧺", status:"PICKED_UP",  photoKey:"pickup"},
    {key:2,label:"세탁 시작",  icon:"🫧", status:"WASHING",    photoKey:null},
    {key:3,label:"건조 완료",  icon:"💨", status:"DRYING",     photoKey:null},
    {key:4,label:"배송 완료",  icon:"✅", status:"COMPLETED",  photoKey:"delivery"},
  ];
  const cls = s => step >= s.key ? "done" : step === s.key - 1 ? "active" : "pending";

  async function handleStep(s) {
    if (s.photoKey && !photos[s.photoKey]) {
      setToast("📷 사진 먼저 촬영해 주세요"); return;
    }
    if (!activeOrder) { setToast("진행중인 주문이 없습니다"); return; }
    setLoading(true);
    try {
      await orderApi.updateStatus(activeOrder.id, s.status);
      setStep(s.key);
      setToast(s.key === 4 ? "🎉 배송 완료! 정산 처리됩니다" : `✅ ${s.label}`);
    } catch(e) { setToast(`❌ ${e.message}`); }
    finally { setLoading(false); }
  }

  async function handlePhotoUpload(photoKey) {
    const input = document.createElement("input");
    input.type = "file"; input.accept = "image/*"; input.capture = "environment";
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file || !activeOrder) return;
      try {
        const pType = photoKey === "pickup" ? "PICKUP" : "DELIVERY";
        await orderApi.uploadPhoto(activeOrder.id, pType, file);
        setPhotos(ph => ({...ph, [photoKey]: true}));
        setToast("📷 S3 업로드 완료");
      } catch(e) { setToast(`❌ ${e.message}`); }
    };
    input.click();
  }

  return (
    <><style>{CSS}</style>
    <div className="app fu">
      <TopBar/>
      <div className="screen">
        <div style={{padding:"13px 13px 0"}}>
          <div className="cd-wrap">
            <div style={{fontSize:10,color:"#555",marginBottom:3}}>SLA 마감까지</div>
            <div className="cd-val">{countdown || "--:--:--"}</div>
            {activeOrder && <div style={{fontSize:11,color:"#444",marginTop:3}}>{new Date(activeOrder.deadline_at).toLocaleString("ko-KR")} 배송 완료 목표</div>}
          </div>
          {activeOrder ? (
            <div className="card" style={{marginBottom:11}}>
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:6}}>
                <span style={{fontFamily:"monospace",fontSize:11,color:"#888"}}>{activeOrder.id?.slice(0,8)}</span>
                <span className={`badge ${activeOrder.service_type==="DAY"?"b-yellow":"b-purple"}`}>{activeOrder.service_type}</span>
              </div>
              <div style={{fontSize:13,fontWeight:700,marginBottom:2}}>{activeOrder.pickup_address}</div>
              <div style={{fontSize:11,color:"#888",marginBottom:9}}>{activeOrder.wash_category} · 예상 수익 {(activeOrder.total_amount-1000).toLocaleString()}원</div>
            </div>
          ) : (
            <div style={{textAlign:"center",padding:24,color:"#888",fontSize:13}}>진행중인 주문이 없습니다</div>
          )}
          <div style={{fontSize:11,color:"#666",fontWeight:700,textTransform:"uppercase",letterSpacing:".5px",marginBottom:8}}>작업 단계</div>
          <div className="step-grid" style={{marginBottom:11}}>
            {STEPS.map(s=>(
              <button key={s.key} className={`step-btn ${cls(s)}`} disabled={loading}
                onClick={()=>handleStep(s)}>
                <div style={{fontSize:20,marginBottom:4}}>{s.icon}</div>{step>=s.key?"✅ ":""}{s.label}
              </button>
            ))}
          </div>
          <div style={{fontSize:11,color:"#666",fontWeight:700,textTransform:"uppercase",letterSpacing:".5px",marginBottom:8}}>📷 증빙 사진 (필수)</div>
          <div style={{display:"flex",gap:9,marginBottom:11}}>
            {[{key:"pickup",label:"수거 시",icon:"🧺"},{key:"delivery",label:"배송 완료",icon:"📦"}].map(p=>(
              <div key={p.key} className={`photo ${photos[p.key]?"up":""}`} style={{flex:1}}
                onClick={()=>handlePhotoUpload(p.key)}>
                <span style={{fontSize:24}}>{photos[p.key]?"✅":p.icon}</span>
                <span style={{fontSize:10,fontWeight:600,color:photos[p.key]?"var(--green)":"#888"}}>{photos[p.key]?"완료":p.label}</span>
                {!photos[p.key]&&<span className="badge b-red" style={{fontSize:9}}>필수</span>}
              </div>
            ))}
          </div>
          <div style={{background:"var(--blue-l)",borderRadius:10,padding:"9px 12px",fontSize:11,color:"var(--blue)"}}>ℹ️ 사진은 촬영 시각·위치가 자동 기록됩니다</div>
        </div>
      </div>
      <BottomNav active={1}/>
      {toast&&<Toast msg={toast} onHide={()=>setToast(null)}/>}
    </div></>
  );
}

function HistoryScreen() {
  const { partner } = useAuth();
  const [tab, setTab] = useState(0);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    orderApi.list().then(data => {
      setOrders(data.filter(o => o.status === "COMPLETED"));
    }).catch(()=>{}).finally(() => setLoading(false));
  }, []);

  const totalRevenue = orders.reduce((s, o) => s + (o.total_amount - 1000), 0);

  return (
    <><style>{CSS}</style>
    <div className="app fu">
      <TopBar/>
      <div className="screen">
        <div style={{padding:"13px 13px 0"}}>
          <div className="tabs">{["전체","이번 주","이번 달"].map((t,i)=><button key={i} className={`tab ${tab===i?"active":""}`} onClick={()=>setTab(i)}>{t}</button>)}</div>
          <div style={{background:"#111",borderRadius:13,padding:"13px 15px 17px",marginBottom:11}}>
            <div style={{display:"flex",gap:9}}>
              <div style={{flex:1,background:"#1a1a1a",borderRadius:12,padding:"11px 12px",border:"1px solid #222"}}>
                <div className="earn-lbl" style={{fontSize:10,color:"#444",textTransform:"uppercase",letterSpacing:".5px",marginBottom:3}}>총 수입</div>
                <div style={{fontFamily:"var(--fd)",fontSize:17,fontWeight:800,color:"var(--yellow)"}}>{totalRevenue.toLocaleString()}원</div>
              </div>
              <div style={{flex:1,background:"#1a1a1a",borderRadius:12,padding:"11px 12px",border:"1px solid #222"}}>
                <div className="earn-lbl" style={{fontSize:10,color:"#444",textTransform:"uppercase",letterSpacing:".5px",marginBottom:3}}>처리 건수</div>
                <div style={{fontFamily:"var(--fd)",fontSize:17,fontWeight:800,color:"white"}}>{orders.length}건</div>
              </div>
            </div>
          </div>
          {loading && <div style={{display:"flex",justifyContent:"center",padding:24}}><div className="spinner"/></div>}
          {orders.map((r,i)=>(
            <div key={i} className="hist">
              <div style={{display:"flex",justifyContent:"space-between",marginBottom:4}}>
                <span style={{fontFamily:"monospace",fontSize:10,color:"#888"}}>{r.id?.slice(0,8)}</span>
                <span style={{fontSize:10,color:"#888"}}>{r.completed_at?.slice(11,16)}</span>
              </div>
              <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                <div style={{display:"flex",alignItems:"center",gap:6}}>
                  <span style={{fontWeight:700,fontSize:13}}>{r.pickup_address?.slice(0,15)}</span>
                  <span className={`badge ${r.service_type==="NIGHT"?"b-purple":"b-yellow"}`}>{r.service_type}</span>
                </div>
                <div style={{fontFamily:"var(--fd)",fontWeight:800,fontSize:14,color:"var(--blue)"}}>+{(r.total_amount-1000).toLocaleString()}원</div>
              </div>
            </div>
          ))}
          {!loading && orders.length === 0 && (
            <div style={{textAlign:"center",padding:32,color:"#888",fontSize:13}}>완료된 주문이 없습니다</div>
          )}
        </div>
      </div>
      <BottomNav active={2}/>
    </div></>
  );
}

function SettlementScreen() {
  const { partner, logout } = useAuth(); const { navigate } = useRouter();
  const [settlements, setSettlements] = useState([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!partner?.shopId) return;
    settlementApi.list(partner.shopId).then(data => {
      setSettlements(data);
    }).catch(()=>{}).finally(() => setLoading(false));
  }, [partner?.shopId]);

  const selected = settlements[selectedIdx];

  return (
    <><style>{CSS}</style>
    <div className="app fu">
      <TopBar/>
      <div className="screen">
        <div style={{padding:"13px 13px 0"}}>
          {loading
            ? <div style={{display:"flex",justifyContent:"center",padding:32}}><div className="spinner"/></div>
            : <>
              {settlements.length > 0 && (
                <div className="tabs">
                  {settlements.slice(0,3).map((s,i)=>(
                    <button key={i} className={`tab ${selectedIdx===i?"active":""}`} onClick={()=>setSelectedIdx(i)}>
                      {s.period_start?.slice(5)}~{s.period_end?.slice(5)}
                    </button>
                  ))}
                </div>
              )}
              {selected && <>
                <div className="settle-card">
                  <div style={{fontSize:10,color:"#555",marginBottom:4}}>정산 기간: {selected.period_start} ~ {selected.period_end}</div>
                  <div className="settle-val">{selected.net_payout?.toLocaleString()}원</div>
                  <div style={{fontSize:11,color:"#555",marginTop:5}}>
                    {selected.status === "PAID" ? `지급완료 ✅` : `${selected.payout_date ?? "지급 예정"}`}
                  </div>
                </div>
                <div className="card" style={{marginBottom:11}}>
                  <div className="card-title">수익 명세</div>
                  {[
                    ["완료 건수", `${selected.order_count}건`],
                    ["총 매출", `${selected.total_sales?.toLocaleString()}원`],
                    [`플랫폼 수수료 (×1,000원)`, `-${selected.platform_fee?.toLocaleString()}원`],
                    ["최종 정산액", `${selected.net_payout?.toLocaleString()}원`],
                  ].map(([l,v],i)=>(
                    <div key={i} className="data-row">
                      <span style={{color:"#888"}}>{l}</span>
                      <span style={{fontWeight:700,color:i===3?"var(--yellow)":i===2?"var(--red)":"inherit"}}>{v}</span>
                    </div>
                  ))}
                </div>
              </>}
              {settlements.length === 0 && (
                <div style={{textAlign:"center",padding:32,color:"#888",fontSize:13}}>정산 내역이 없습니다</div>
              )}
            </>
          }
          <button onClick={()=>{logout();navigate("/login");}} style={{width:"100%",background:"transparent",border:"1px solid #333",borderRadius:12,padding:"13px",fontSize:13,fontWeight:700,color:"#555",cursor:"pointer",marginBottom:20,marginTop:12}}>로그아웃</button>
        </div>
      </div>
      <BottomNav active={3}/>
    </div></>
  );
}

// ─── Route Switch & Root ──────────────────────────────────────────────────────
function RouteSwitch() {
  const { path } = useRouter();
  const map = {"/login":LoginScreen,"/orders":OrdersScreen,"/task":TaskScreen,"/history":HistoryScreen,"/settlement":SettlementScreen};
  const C = map[path] || LoginScreen;
  return <C/>;
}

export default function PartnerApp() {
  return (
    <Router>
      <AuthProvider>
        <RouteSwitch/>
      </AuthProvider>
    </Router>
  );
}
