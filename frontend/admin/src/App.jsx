/**
 * ╔══════════════════════════════════════════════════════════╗
 * ║  세팡 관리자 어드민  |  admin.internal.sepang.kr         ║
 * ║  배포: Private VPC 내부망 전용 — 외부 노출 없음         ║
 * ║  접근: VPN 필수 (10.0.0.0/8) + OTP 2단계 인증          ║
 * ╚══════════════════════════════════════════════════════════╝
 */
import { useState, useEffect, createContext, useContext, useCallback } from "react";
import { adminApi, authApi, tokenStore } from "@sepang/shared/lib/api-client";

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
  const [admin, setAdmin] = useState(null);
  return (
    <AuthCtx.Provider value={{ admin, login: (a) => setAdmin(a), logout: () => { authApi.logout(); setAdmin(null); navigate("/login"); } }}>
      {children}
    </AuthCtx.Provider>
  );
}

// ─── 데이터 페칭 훅 ───────────────────────────────────────────────────────────
function useApi(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await fetcher();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => { load(); }, [load]);
  return { data, loading, error, reload: load };
}

// ─── CSS ──────────────────────────────────────────────────────────────────────
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&family=Syne:wght@700;800&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --blue:#0057FF; --blue-l:#EEF3FF; --blue-dark:#003DC7;
    --yellow:#FFD600; --green:#00C853; --red:#FF3D00;
    --purple:#7C4DFF; --surface:#F6F7FB; --border:#E8E8E8;
    --font-d:'Syne',sans-serif; --font-b:'Noto Sans KR',sans-serif;
  }
  html, body, #root { height: 100%; font-family: var(--font-b); background: var(--surface); -webkit-font-smoothing: antialiased; }
  button { font-family: var(--font-b); cursor: pointer; border: none; }
  input { font-family: var(--font-b); }
  ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: #e0e0e0; border-radius: 2px; }
  @keyframes fadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
  .fu { animation: fadeUp .3s ease both; }
  .shell { display: flex; min-height: 100vh; background: var(--surface); }
  .sidebar { width: 220px; min-width: 220px; background: #0D0D0D; display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh; }
  .sb-logo { padding: 18px 16px 14px; border-bottom: 1px solid #1a1a1a; }
  .sb-logo-text { font-family: var(--font-d); font-size: 20px; font-weight: 800; color: white; }
  .sb-logo-text em { color: var(--yellow); font-style: normal; }
  .sb-logo-sub { font-size: 9px; color: #2a2a2a; text-transform: uppercase; letter-spacing: 1.5px; margin-top: 2px; }
  .internal-tag { margin: 8px 10px; background: #1a0000; border: 1px solid #3a0000; border-radius: 7px; padding: 5px 9px; font-size: 10px; color: #FF6B6B; }
  .sb-nav { padding: 8px 6px; flex: 1; overflow-y: auto; }
  .sb-grp { font-size: 9px; color: #2a2a2a; text-transform: uppercase; letter-spacing: 1.8px; padding: 0 8px; margin: 12px 0 3px; }
  .sb-link { display: flex; align-items: center; gap: 8px; padding: 8px 9px; border-radius: 7px; font-size: 12px; color: #555; cursor: pointer; transition: all .15s; margin-bottom: 1px; }
  .sb-link:hover { background: #161616; color: white; }
  .sb-link.active { background: var(--blue); color: white; }
  .sb-badge { margin-left: auto; background: var(--red); color: white; font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 8px; }
  .main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .topbar { height: 50px; background: white; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 20px; flex-shrink: 0; position: sticky; top: 0; z-index: 40; }
  .topbar-title { font-size: 14px; font-weight: 700; }
  .a-tag { font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 20px; background: #FFF0ED; color: var(--red); }
  .page { padding: 20px; overflow-y: auto; flex: 1; }
  .kpi-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin-bottom: 14px; }
  .kpi { background: white; border-radius: 12px; border: 1px solid var(--border); padding: 14px 15px; position: relative; overflow: hidden; }
  .kpi::after { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; }
  .kpi.blue::after{background:var(--blue);} .kpi.green::after{background:var(--green);} .kpi.yellow::after{background:var(--yellow);} .kpi.red::after{background:var(--red);}
  .kpi-lbl { font-size: 10px; color: #888; margin-bottom: 6px; }
  .kpi-val { font-family: var(--font-d); font-size: 22px; font-weight: 800; line-height: 1; }
  .kpi-delta { font-size: 10px; margin-top: 4px; }
  .kpi-icon { position: absolute; right: 12px; top: 12px; font-size: 22px; opacity: .1; }
  .g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
  .g3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 12px; }
  .g21 { display: grid; grid-template-columns: 2fr 1fr; gap: 10px; margin-bottom: 12px; }
  .card { background: white; border-radius: 12px; border: 1px solid var(--border); padding: 15px 17px; }
  .card-title { font-size: 12px; font-weight: 700; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
  .tbl { width: 100%; border-collapse: collapse; }
  .tbl th { font-size: 10px; color: #888; font-weight: 500; text-align: left; padding: 0 7px 8px; border-bottom: 1px solid var(--border); }
  .tbl td { font-size: 12px; padding: 9px 7px; border-bottom: 1px solid #F8F8F8; }
  .tbl tbody tr:hover td { background: #FAFBFF; }
  .tbl tbody tr:last-child td { border-bottom: none; }
  .badge { display: inline-flex; align-items: center; gap: 2px; padding: 2px 7px; border-radius: 20px; font-size: 10px; font-weight: 600; }
  .ab-blue{background:var(--blue-l);color:var(--blue);} .ab-green{background:#E8F5E9;color:#2E7D32;}
  .ab-yellow{background:#FFF8E1;color:#B07800;} .ab-red{background:#FFF0ED;color:var(--red);}
  .ab-purple{background:#F3E5F5;color:var(--purple);} .ab-gray{background:#F5F5F5;color:#666;}
  .btn { border: none; border-radius: 7px; font-weight: 700; cursor: pointer; font-family: var(--font-b); font-size: 11px; padding: 5px 11px; }
  .btn-primary{background:var(--blue);color:white;} .btn-outline{background:transparent;border:1.5px solid var(--border);color:#444;}
  .btn-danger{background:var(--red);color:white;} .btn-ghost{background:transparent;color:var(--blue);font-size:11px;font-weight:700;border:none;padding:4px 8px;cursor:pointer;}
  .alert-red { background:#FFF0ED; border:1px solid #FFCDD2; border-radius:9px; padding:9px 13px; font-size:12px; color:#C62828; display:flex; align-items:center; gap:8px; margin-bottom:7px; }
  .alert-warn { background:#FFFBF0; border:1px solid #FFE0B2; border-radius:9px; padding:9px 13px; font-size:12px; color:#E65100; display:flex; align-items:center; gap:8px; margin-bottom:7px; }
  .bars { display:flex; align-items:flex-end; gap:5px; height:100px; }
  .bar-col { display:flex; flex-direction:column; align-items:center; gap:3px; flex:1; }
  .bar-pair { display:flex; gap:2px; align-items:flex-end; }
  .bar { border-radius:3px 3px 0 0; width:11px; min-height:3px; }
  .fn-row { display:flex; align-items:center; gap:7px; margin-bottom:6px; }
  .fn-lbl { font-size:10px; color:#888; width:60px; text-align:right; }
  .fn-bg { flex:1; height:20px; background:var(--surface); border-radius:4px; overflow:hidden; }
  .fn-fill { height:100%; border-radius:4px; display:flex; align-items:center; padding-left:7px; font-size:9px; font-weight:700; color:white; }
  .fn-cnt { font-size:10px; font-weight:700; width:32px; }
  .login-wrap { min-height:100vh; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg,#050505 0%,#070D1A 100%); }
  .login-box { background:#0D0D0D; border-radius:18px; padding:32px; width:360px; border:1px solid #1a1a1a; box-shadow:0 32px 80px rgba(0,0,0,.7); }
  .spinner { display:inline-block; width:14px; height:14px; border:2px solid #E8E8E8; border-top-color:var(--blue); border-radius:50%; animation:spin .6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .error-box { background:#FFF0ED; border:1px solid #FFCDD2; border-radius:9px; padding:9px 13px; font-size:12px; color:#C62828; margin-bottom:10px; }
  .modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,.45); z-index:200; display:flex; align-items:center; justify-content:center; }
  .modal { background:white; border-radius:16px; padding:24px 28px; width:500px; max-width:96vw; max-height:90vh; overflow-y:auto; box-shadow:0 24px 64px rgba(0,0,0,.18); }
  .modal-title { font-size:15px; font-weight:700; margin-bottom:18px; display:flex; align-items:center; justify-content:space-between; }
  .form-row { margin-bottom:11px; }
  .form-label { font-size:11px; color:#666; font-weight:600; margin-bottom:4px; display:block; }
  .form-input { width:100%; padding:9px 11px; border:1.5px solid var(--border); border-radius:8px; font-size:12px; font-family:var(--font-b); outline:none; transition:border-color .15s; }
  .form-input:focus { border-color:var(--blue); }
  .form-select { width:100%; padding:9px 11px; border:1.5px solid var(--border); border-radius:8px; font-size:12px; font-family:var(--font-b); background:white; outline:none; }
  .form-row2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:11px; }
  .form-section { font-size:10px; font-weight:700; color:#aaa; text-transform:uppercase; letter-spacing:1.2px; margin:16px 0 10px; padding-top:14px; border-top:1px solid var(--border); }
`;

const NAV = [
  {group:"운영",items:[{to:"/dashboard",ico:"📊",label:"대시보드"},{to:"/orders",ico:"📦",label:"주문 관제",badge:"sla"},{to:"/shops",ico:"🏪",label:"점포 관리"}]},
  {group:"재무",items:[{to:"/settlements",ico:"💳",label:"정산 관리"}]},
  {group:"마케팅",items:[{to:"/marketing",ico:"📣",label:"마케팅/CRM"},{to:"/analytics",ico:"📈",label:"분석"}]},
  {group:"시스템",items:[{to:"/settings",ico:"⚙️",label:"설정"},{to:"/logs",ico:"📋",label:"접근 로그"}]},
];

// ─── Shared Components ────────────────────────────────────────────────────────
function StatusBadge({ s }) {
  const M={PENDING:["ab-yellow","⏳","수거대기"],ACCEPTED:["ab-blue","✋","수락"],PICKED_UP:["ab-blue","🧺","수거완료"],WASHING:["ab-blue","🫧","세탁중"],DRYING:["ab-purple","💨","건조중"],DELIVERING:["ab-green","🚗","배송중"],COMPLETED:["ab-green","✅","완료"],CANCELLED:["ab-gray","❌","취소"]};
  const [cls,icon,label]=M[s]||["ab-gray","?",s];
  return <span className={`badge ${cls}`}>{icon} {label}</span>;
}

function Timer({ hours_left }) {
  if (hours_left === null || hours_left === undefined) return <span style={{color:"#00C853",fontWeight:700,fontSize:11}}>✅</span>;
  const h = Math.floor(hours_left);
  const m = Math.floor((hours_left - h) * 60);
  const display = `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;
  const col = h < 1 ? "#FF3D00" : h < 2 ? "#E65100" : "#0057FF";
  return <span style={{color:col,fontWeight:700,fontFamily:"'Syne',sans-serif",fontSize:12}}>{display}</span>;
}

function Spinner() {
  return <div style={{display:"flex",justifyContent:"center",padding:32}}><div className="spinner"/></div>;
}

function ErrorBox({ msg }) {
  return <div className="error-box">⚠️ {msg}</div>;
}

function Layout({ title, children, slaCount = 0 }) {
  const { path, navigate } = useRouter();
  const { admin, logout } = useAuth();
  return (
    <div className="shell">
      <div className="sidebar">
        <div className="sb-logo">
          <div className="sb-logo-text">세<em>팡</em></div>
          <div className="sb-logo-sub">Admin Console</div>
        </div>
        <div className="internal-tag">🔒 내부 전용 시스템</div>
        <div className="sb-nav">
          {NAV.map((g,gi)=>(
            <div key={gi}>
              <div className="sb-grp">{g.group}</div>
              {g.items.map(it=>(
                <div key={it.to} className={`sb-link ${path===it.to?"active":""}`} onClick={()=>navigate(it.to)}>
                  <span style={{fontSize:13,width:16,textAlign:"center"}}>{it.ico}</span>
                  <span>{it.label}</span>
                  {it.badge==="sla" && slaCount > 0 && <span className="sb-badge">{slaCount}</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
        <div style={{padding:"10px 6px",borderTop:"1px solid #1a1a1a"}}>
          <div style={{display:"flex",alignItems:"center",gap:8,padding:"7px 8px",borderRadius:7}}>
            <div style={{width:28,height:28,borderRadius:"50%",background:"#0057FF",display:"flex",alignItems:"center",justifyContent:"center",color:"white",fontSize:10,fontWeight:700,flexShrink:0}}>관</div>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontSize:11,color:"white",fontWeight:600,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{admin?.name||"관리자"}</div>
              <div style={{fontSize:9,color:"#444"}}>{admin?.email||""}</div>
            </div>
            <button
              onClick={() => { if (window.confirm("로그아웃 하시겠습니까?")) logout(); }}
              style={{flexShrink:0,background:"#1a1a1a",border:"1px solid #2a2a2a",borderRadius:6,color:"#666",fontSize:10,padding:"4px 8px",cursor:"pointer",whiteSpace:"nowrap"}}>
              로그아웃
            </button>
          </div>
        </div>
      </div>
      <div className="main">
        <div className="topbar">
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <span className="topbar-title">{title}</span>
            <span className="a-tag">🔒 Internal</span>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <span style={{fontFamily:"monospace",fontSize:10,color:"#888",background:"#F6F7FB",padding:"2px 7px",borderRadius:5}}>{path}</span>
          </div>
        </div>
        <div className="page">{children}</div>
      </div>
    </div>
  );
}

// ─── Pages ────────────────────────────────────────────────────────────────────
function LoginPage() {
  const { navigate } = useRouter(); const { login } = useAuth();
  const [step,setStep]=useState(0);
  const [id,setId]=useState(""); const [pw,setPw]=useState(""); const [otp,setOtp]=useState("");
  const [tempToken,setTempToken]=useState(null);
  const [loading,setLoading]=useState(false); const [error,setError]=useState("");
  const is={width:"100%",padding:"10px 12px",border:"1.5px solid #1e1e1e",borderRadius:8,fontSize:12,background:"#070707",color:"white",outline:"none",fontFamily:"inherit",marginBottom:11};

  async function handleStep1() {
    setLoading(true); setError("");
    try {
      const { temp_token } = await authApi.adminLogin(id, pw);
      setTempToken(temp_token);
      setStep(1);
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }

  async function handleStep2() {
    setLoading(true); setError("");
    try {
      const { access_token, refresh_token } = await authApi.adminOtp(tempToken, otp);
      tokenStore.set(access_token, refresh_token);
      login({ name:"관리자", email: id });
      navigate("/dashboard");
    } catch(e) { setError(e.message); }
    finally { setLoading(false); }
  }

  return (
    <><style>{CSS}</style>
    <div className="login-wrap">
      <div className="login-box">
        <div style={{fontFamily:"'Syne',sans-serif",fontSize:26,fontWeight:800,color:"white",marginBottom:3}}>세<span style={{color:"#FFD600"}}>팡</span></div>
        <div style={{display:"flex",alignItems:"center",gap:6,marginBottom:22}}>
          <span style={{background:"#1a0000",border:"1px solid #3a0000",borderRadius:6,padding:"2px 8px",fontSize:10,color:"#FF6B6B",fontWeight:700}}>🔒 INTERNAL</span>
          <span style={{fontSize:11,color:"#333"}}>관리자 전용 콘솔</span>
        </div>
        {error && <div className="error-box">{error}</div>}
        {step===0?(<>
          <div style={{fontSize:11,color:"#444",marginBottom:3}}>관리자 이메일</div>
          <input style={is} placeholder="admin@sepang.kr" value={id} onChange={e=>setId(e.target.value)}/>
          <div style={{fontSize:11,color:"#444",marginBottom:3}}>비밀번호</div>
          <input style={is} type="password" placeholder="••••••••" value={pw} onChange={e=>setPw(e.target.value)}/>
          <button style={{width:"100%",background:"#FFD600",color:"#111",borderRadius:10,padding:"13px",fontSize:14,fontWeight:900,border:"none",cursor:"pointer"}} onClick={handleStep1} disabled={loading}>
            {loading ? <span className="spinner"/> : "다음 →"}
          </button>
        </>):(<>
          <div style={{marginBottom:12,padding:"10px 12px",background:"#070707",borderRadius:8,fontSize:11,color:"#444",lineHeight:1.7}}>
            Google Authenticator OTP를 입력하세요.
          </div>
          <div style={{fontSize:11,color:"#444",marginBottom:3}}>OTP 6자리</div>
          <input style={is} placeholder="000000" maxLength={6} value={otp} onChange={e=>setOtp(e.target.value)}/>
          <button style={{width:"100%",background:"#FFD600",color:"#111",borderRadius:10,padding:"13px",fontSize:14,fontWeight:900,border:"none",cursor:"pointer",marginBottom:8}}
            onClick={handleStep2} disabled={loading}>
            {loading ? <span className="spinner"/> : "콘솔 접속"}
          </button>
          <button style={{width:"100%",background:"transparent",border:"none",color:"#444",fontSize:12,cursor:"pointer",padding:8}} onClick={()=>{setStep(0);setError("");}}>← 뒤로</button>
        </>)}
        <div style={{marginTop:18,padding:11,background:"#070707",borderRadius:9,border:"1px solid #1a1a1a",fontSize:10,color:"#2a2a2a",lineHeight:1.8}}>
          • VPN 연결 필수 (10.0.0.0/8)<br/>• 5회 실패 시 계정 잠금<br/>• 모든 접근 감사 로그 기록
        </div>
      </div>
    </div></>
  );
}

function Dashboard() {
  const { data: kpi, loading, error } = useApi(() => adminApi.dashboard(), []);
  const { data: slaOrders } = useApi(() => adminApi.slaAtRisk(), []);

  if (loading) return <Layout title="대시보드"><style>{CSS}</style><Spinner/></Layout>;
  if (error) return <Layout title="대시보드"><style>{CSS}</style><ErrorBox msg={error}/></Layout>;

  const kpiCards = [
    {l:"오늘 주문",      v: kpi?.today_orders?.toLocaleString() ?? "-",       c:"blue",  i:"📦"},
    {l:"전환율",         v: `${kpi?.conversion_rate ?? 0}%`,                  c:"green", i:"📈"},
    {l:"평균 단가",      v: (kpi?.avg_order_value ?? 0).toLocaleString()+"원", c:"yellow",i:"💰"},
    {l:"SLA 위반",       v: `${kpi?.sla_violations ?? 0}건`,                  c:"red",   i:"⚠️"},
  ];

  return (
    <Layout title="대시보드" slaCount={slaOrders?.length ?? 0}><style>{CSS}</style>
      <div className="kpi-grid">
        {kpiCards.map((k,i)=>(
          <div key={i} className={`kpi ${k.c} fu`} style={{animationDelay:`${i*.05}s`}}>
            <div className="kpi-lbl">{k.l}</div><div className="kpi-val">{k.v}</div>
            <div className="kpi-icon">{k.i}</div>
          </div>
        ))}
      </div>
      <div className="card">
        <div className="card-title">SLA 위험 주문</div>
        {(!slaOrders || slaOrders.length === 0)
          ? <div style={{color:"#00C853",fontSize:12}}>✅ 위험 주문 없음</div>
          : <table className="tbl"><thead><tr><th>주문ID</th><th>잔여시간</th><th>상태</th></tr></thead>
            <tbody>{slaOrders.map((r,i)=>(
              <tr key={i}>
                <td style={{fontFamily:"monospace",fontSize:11,color:"#888"}}>{r.id?.slice(0,8)}</td>
                <td><Timer hours_left={r.hours_left}/></td>
                <td><StatusBadge s={r.status}/></td>
              </tr>
            ))}</tbody></table>
        }
      </div>
    </Layout>
  );
}

function OrdersPage() {
  const [tab,setTab]=useState(0);
  const statusMap = [undefined,"PENDING","COMPLETED","CANCELLED"];
  const { data, loading, error, reload } = useApi(
    () => adminApi.orders({ status: statusMap[tab] }),
    [tab]
  );

  return (
    <Layout title="주문 관제"><style>{CSS}</style>
      <div className="card">
        <div className="card-title">전체 주문 <div style={{display:"flex",gap:6}}>
          <button className="btn btn-primary" onClick={()=>{
            if (!data?.items) return;
            const csv = ["주문번호,고객,점포,타입,상태,금액,시간"].concat(
              data.items.map(r => `${r.id},${r.customer_name},${r.shop_name||""},${r.service_type},${r.status},${r.total_amount},${r.ordered_at}`)
            ).join("\n");
            const a = document.createElement("a");
            a.href = URL.createObjectURL(new Blob([csv], {type:"text/csv"}));
            a.download = "orders.csv"; a.click();
          }}>CSV 내보내기</button>
          <button className="btn btn-outline" onClick={reload}>새로고침</button>
        </div></div>
        <div style={{display:"flex",gap:2,background:"#F6F7FB",borderRadius:9,padding:3,marginBottom:12}}>
          {["전체","대기","완료","취소"].map((t,i)=>(
            <button key={i} onClick={()=>setTab(i)} style={{flex:1,padding:"6px",border:"none",borderRadius:7,fontSize:11,fontWeight:700,color:tab===i?"#0057FF":"#888",background:tab===i?"white":"transparent",cursor:"pointer"}}>
              {t}
            </button>
          ))}
        </div>
        {loading ? <Spinner/> : error ? <ErrorBox msg={error}/> :
          <table className="tbl"><thead><tr><th>주문번호</th><th>고객</th><th>점포</th><th>타입</th><th>상태</th><th>잔여</th><th>금액</th></tr></thead>
          <tbody>{(data?.items ?? []).map((r,i)=>(
            <tr key={i}>
              <td style={{fontFamily:"monospace",fontSize:11,color:"#888"}}>{r.id?.slice(0,8)}</td>
              <td style={{fontWeight:600}}>{r.customer_name}</td>
              <td>{r.shop_name??"-"}</td>
              <td><span className={`badge ${r.service_type==="DAY"?"ab-yellow":"ab-purple"}`}>{r.service_type}</span></td>
              <td><StatusBadge s={r.status}/></td>
              <td><Timer hours_left={r.hours_left}/></td>
              <td style={{fontFamily:"'Syne',sans-serif",fontWeight:700}}>{r.total_amount?.toLocaleString()}원</td>
            </tr>
          ))}</tbody></table>
        }
        {data && <div style={{fontSize:11,color:"#888",marginTop:10}}>총 {data.total}건 / {data.pages}페이지</div>}
      </div>
    </Layout>
  );
}

const EMPTY_SHOP = {
  name:"", address:"", owner_name:"", phone:"", business_number:"", password:"",
  team_type:"DAY", radius_km:"3", bank_name:"", bank_account:"", bank_holder:"",
};

function ShopsPage() {
  const { data: shops, loading, error, reload } = useApi(() => adminApi.shops(), []);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_SHOP);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const totals = shops ? {
    total: shops.length,
    day: shops.filter(s => s.team_type === "DAY").length,
    night: shops.filter(s => s.team_type === "NIGHT").length,
  } : {total:0,day:0,night:0};

  function setField(k, v) { setForm(f => ({...f, [k]: v})); }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError("");
    setSubmitting(true);
    try {
      await adminApi.createShop({
        ...form,
        radius_km: parseFloat(form.radius_km) || 3,
        bank_name:    form.bank_name    || undefined,
        bank_account: form.bank_account || undefined,
        bank_holder:  form.bank_holder  || undefined,
      });
      setShowForm(false);
      setForm(EMPTY_SHOP);
      reload();
    } catch(e) {
      setFormError(e.message || "등록에 실패했습니다");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Layout title="점포 관리"><style>{CSS}</style>
      <div className="g3">
        {[{l:"전체 점포",v:`${totals.total}개`,c:"blue",i:"🏪"},{l:"Day 팀",v:`${totals.day}개`,c:"yellow",i:"☀️"},{l:"Night 팀",v:`${totals.night}개`,c:"blue",i:"🌙"}].map((k,i)=>(
          <div key={i} className={`kpi ${k.c}`}><div className="kpi-lbl">{k.l}</div><div className="kpi-val" style={{fontSize:20}}>{k.v}</div><div className="kpi-icon">{k.i}</div></div>
        ))}
      </div>
      <div className="card">
        <div className="card-title">
          제휴 점포 현황
          <button className="btn btn-primary" onClick={() => { setForm(EMPTY_SHOP); setFormError(""); setShowForm(true); }}>+ 점포 등록</button>
        </div>
        {loading ? <Spinner/> : error ? <ErrorBox msg={error}/> :
          <table className="tbl"><thead><tr><th>점포명</th><th>지역</th><th>팀</th><th>오늘</th><th>평점</th><th>상태</th></tr></thead>
          <tbody>{(shops??[]).map((s,i)=>(
            <tr key={i}>
              <td style={{fontWeight:600}}>{s.name}</td>
              <td style={{color:"#888",fontSize:11}}>{s.region}</td>
              <td><span className={`badge ${s.team_type==="NIGHT"?"ab-purple":s.team_type==="BOTH"?"ab-blue":"ab-yellow"}`}>{s.team_type}</span></td>
              <td style={{fontFamily:"'Syne',sans-serif",fontWeight:700}}>{s.today_orders}건</td>
              <td>⭐ {s.rating?.toFixed(1)}</td>
              <td><span className={`badge ${s.is_active?"ab-green":"ab-gray"}`}>{s.is_active?"운영중":"휴식"}</span></td>
            </tr>
          ))}</tbody></table>
        }
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={e => e.target === e.currentTarget && setShowForm(false)}>
          <div className="modal fu">
            <div className="modal-title">
              🏪 점포 등록
              <button className="btn btn-ghost" onClick={() => setShowForm(false)} style={{fontSize:18,padding:"2px 8px",color:"#888"}}>✕</button>
            </div>
            {formError && <div className="error-box">{formError}</div>}
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <label className="form-label">점포명 *</label>
                <input className="form-input" placeholder="예: 세팡 강남점" value={form.name} onChange={e=>setField("name",e.target.value)} required/>
              </div>
              <div className="form-row">
                <label className="form-label">주소 *</label>
                <input className="form-input" placeholder="예: 서울특별시 강남구 테헤란로 123" value={form.address} onChange={e=>setField("address",e.target.value)} required/>
              </div>
              <div className="form-row2">
                <div className="form-row" style={{marginBottom:0}}>
                  <label className="form-label">대표자명 *</label>
                  <input className="form-input" placeholder="홍길동" value={form.owner_name} onChange={e=>setField("owner_name",e.target.value)} required/>
                </div>
                <div className="form-row" style={{marginBottom:0}}>
                  <label className="form-label">연락처 * (010XXXXXXXX)</label>
                  <input className="form-input" placeholder="01012345678" value={form.phone} onChange={e=>setField("phone",e.target.value)} required pattern="^010\d{8}$"/>
                </div>
              </div>
              <div className="form-row2">
                <div className="form-row" style={{marginBottom:0}}>
                  <label className="form-label">사업자번호 * (XXX-XX-XXXXX)</label>
                  <input className="form-input" placeholder="123-45-67890" value={form.business_number} onChange={e=>setField("business_number",e.target.value)} required pattern="^\d{3}-\d{2}-\d{5}$"/>
                </div>
                <div className="form-row" style={{marginBottom:0}}>
                  <label className="form-label">임시 비밀번호 * (8자 이상)</label>
                  <input className="form-input" type="password" placeholder="••••••••" value={form.password} onChange={e=>setField("password",e.target.value)} required minLength={8}/>
                </div>
              </div>
              <div className="form-row2">
                <div className="form-row" style={{marginBottom:0}}>
                  <label className="form-label">팀 유형 *</label>
                  <select className="form-select" value={form.team_type} onChange={e=>setField("team_type",e.target.value)}>
                    <option value="DAY">DAY (주간)</option>
                    <option value="NIGHT">NIGHT (야간)</option>
                    <option value="BOTH">BOTH (전체)</option>
                  </select>
                </div>
                <div className="form-row" style={{marginBottom:0}}>
                  <label className="form-label">서비스 반경 (km)</label>
                  <input className="form-input" type="number" min="1" max="20" step="0.5" value={form.radius_km} onChange={e=>setField("radius_km",e.target.value)}/>
                </div>
              </div>
              <div className="form-section">정산 계좌 (선택)</div>
              <div className="form-row2">
                <div className="form-row" style={{marginBottom:0}}>
                  <label className="form-label">은행명</label>
                  <input className="form-input" placeholder="예: 국민은행" value={form.bank_name} onChange={e=>setField("bank_name",e.target.value)}/>
                </div>
                <div className="form-row" style={{marginBottom:0}}>
                  <label className="form-label">예금주</label>
                  <input className="form-input" placeholder="홍길동" value={form.bank_holder} onChange={e=>setField("bank_holder",e.target.value)}/>
                </div>
              </div>
              <div className="form-row">
                <label className="form-label">계좌번호</label>
                <input className="form-input" placeholder="000-000-000000" value={form.bank_account} onChange={e=>setField("bank_account",e.target.value)}/>
              </div>
              <div style={{display:"flex",gap:10,marginTop:18,justifyContent:"flex-end"}}>
                <button type="button" className="btn btn-outline" onClick={() => setShowForm(false)} disabled={submitting}>취소</button>
                <button type="submit" className="btn btn-primary" disabled={submitting} style={{minWidth:90}}>
                  {submitting ? <span className="spinner"/> : "점포 등록"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </Layout>
  );
}

function SettlementsPage() {
  const { data: settlements, loading, error, reload } = useApi(() => adminApi.settlements(), []);
  const [paying, setPaying] = useState({});

  const totals = settlements ? {
    payout: settlements.reduce((s,r) => s + r.net_payout, 0),
    fee: settlements.reduce((s,r) => s + r.platform_fee, 0),
    pending: settlements.filter(s => s.status === "PENDING").length,
  } : {payout:0, fee:0, pending:0};

  async function handlePay(id) {
    if (!window.confirm("이 정산을 지급 완료로 처리하시겠습니까?")) return;
    setPaying(p => ({...p, [id]: true}));
    try {
      await adminApi.markSettlementPaid(id);
      reload();
    } catch(e) {
      alert(e.message || "처리에 실패했습니다");
    } finally {
      setPaying(p => ({...p, [id]: false}));
    }
  }

  return (
    <Layout title="정산 관리"><style>{CSS}</style>
      <div className="kpi-grid">
        {[
          {l:"총 정산액",    v:`${totals.payout.toLocaleString()}원`, c:"blue"},
          {l:"플랫폼 수수료",v:`${totals.fee.toLocaleString()}원`,    c:"green"},
          {l:"정산 건수",    v:`${settlements?.length??0}건`,          c:"yellow"},
          {l:"미지급 건수",  v:`${totals.pending}건`,                  c:"red"},
        ].map((k,i)=>(
          <div key={i} className={`kpi ${k.c}`}><div className="kpi-lbl">{k.l}</div><div className="kpi-val" style={{fontSize:18}}>{k.v}</div></div>
        ))}
      </div>
      <div className="card">
        <div className="card-title">점포별 정산</div>
        {loading ? <Spinner/> : error ? <ErrorBox msg={error}/> :
          <table className="tbl">
            <thead><tr><th>점포명</th><th>기간</th><th>건수</th><th>총 매출</th><th>수수료</th><th>정산액</th><th>상태</th><th>처리</th></tr></thead>
            <tbody>{(settlements??[]).map((s,i)=>(
              <tr key={i}>
                <td style={{fontWeight:600}}>{s.shop_name}</td>
                <td style={{fontSize:11,color:"#888"}}>{s.period_start}~{s.period_end}</td>
                <td style={{fontFamily:"'Syne',sans-serif",fontWeight:700}}>{s.order_count}건</td>
                <td>{s.total_sales?.toLocaleString()}원</td>
                <td style={{color:"#FF3D00"}}>-{s.platform_fee?.toLocaleString()}원</td>
                <td style={{fontFamily:"'Syne',sans-serif",fontWeight:700,color:"#0057FF"}}>{s.net_payout?.toLocaleString()}원</td>
                <td><span className={`badge ${s.status==="PAID"?"ab-green":"ab-yellow"}`}>{s.status==="PAID"?"지급완료":"대기중"}</span></td>
                <td>
                  {s.status === "PENDING"
                    ? <button className="btn btn-primary" onClick={() => handlePay(s.id)} disabled={paying[s.id]}>
                        {paying[s.id] ? <span className="spinner"/> : "지급 처리"}
                      </button>
                    : <span style={{fontSize:11,color:"#888"}}>완료</span>
                  }
                </td>
              </tr>
            ))}</tbody>
          </table>
        }
      </div>
    </Layout>
  );
}

function LogsPage() {
  const { data: logs, loading, error } = useApi(() => adminApi.auditLogs(), []);
  return (
    <Layout title="접근 로그"><style>{CSS}</style>
      <div style={{background:"#EEF3FF",border:"1px solid #C5D8FF",borderRadius:9,padding:"9px 13px",fontSize:11,color:"#0057FF",marginBottom:12}}>ℹ️ 모든 관리자 접근은 감사 로그에 기록됩니다. 보관 기간: 1년</div>
      <div className="card">
        <div className="card-title">최근 접근 기록</div>
        {loading ? <Spinner/> : error ? <ErrorBox msg={error}/> :
          <table className="tbl"><thead><tr><th>시각</th><th>관리자</th><th>IP</th><th>페이지</th><th>액션</th></tr></thead>
          <tbody>{(logs??[]).map((r,i)=>(
            <tr key={i}>
              <td style={{fontFamily:"monospace",fontSize:11,color:"#888"}}>{r.created_at?.slice(11,19)}</td>
              <td style={{fontWeight:600,fontSize:11}}>{r.admin_email}</td>
              <td style={{fontFamily:"monospace",fontSize:10,color:"#888"}}>{r.ip_address}</td>
              <td style={{fontFamily:"monospace",fontSize:11}}>{r.path}</td>
              <td><span className="badge ab-gray">{r.action}</span></td>
            </tr>
          ))}</tbody></table>
        }
      </div>
    </Layout>
  );
}

function MarketingPage() {
  return (
    <Layout title="마케팅/CRM"><style>{CSS}</style>
      <div className="card">
        <div className="card-title">CRM 자동 푸시 시나리오</div>
        <div style={{color:"#888",fontSize:12,padding:"20px 0",textAlign:"center"}}>Celery Beat 스케줄에 의해 자동 실행됩니다.<br/>tasks.py에서 CRM 시나리오를 관리하세요.</div>
        {[{seg:"가입 후 미주문 3일",trigger:"가입 D+3 09:00",msg:"🎁 첫 주문 할인",st:"SCHEDULED"},
          {seg:"금요일 Night 이용자",trigger:"금요일 20:00",msg:"🌙 주말 알림",st:"SCHEDULED"},
          {seg:"D+0 신규 가입 웰컴",trigger:"즉시",msg:"🎉 웰컴 쿠폰",st:"ACTIVE"},
        ].map((c,i)=>(
          <div key={i} style={{display:"flex",justifyContent:"space-between",padding:"9px 0",borderBottom:"1px solid #F8F8F8",fontSize:12}}>
            <div><div style={{fontWeight:700}}>{c.seg}</div><div style={{fontSize:10,color:"#888"}}>{c.trigger} · {c.msg}</div></div>
            <span className={`badge ${c.st==="ACTIVE"?"ab-green":"ab-blue"}`}>{c.st==="ACTIVE"?"실행중":"예약중"}</span>
          </div>
        ))}
      </div>
    </Layout>
  );
}

function AnalyticsPage() {
  const { data: kpi, loading: kpiLoading } = useApi(() => adminApi.dashboard());
  const { data: shops, loading: shopsLoading } = useApi(() => adminApi.shops());
  const { data: slaRisk, loading: slaLoading } = useApi(() => adminApi.slaAtRisk());
  const { data: settlements } = useApi(() => adminApi.settlements());

  const topShops = (shops || []).slice().sort((a, b) => b.today_orders - a.today_orders).slice(0, 5);
  const settleList = (settlements || []).slice(0, 6);
  const maxSales = settleList.length ? Math.max(...settleList.map(s => s.total_sales || 0), 1) : 1;

  const slaRows = (slaRisk || []).slice(0, 10);

  return (
    <Layout title="분석 대시보드"><style>{CSS}</style>
      {/* KPI 카드 */}
      <div className="kpi-grid">
        {[
          { lbl:"오늘 주문", val: kpiLoading ? "…" : (kpi?.today_orders ?? 0), unit:"건", color:"blue", icon:"📦" },
          { lbl:"완료율", val: kpiLoading ? "…" : `${kpi?.conversion_rate ?? 0}`, unit:"%", color:"green", icon:"✅" },
          { lbl:"주간 매출", val: kpiLoading ? "…" : ((kpi?.week_revenue ?? 0) / 10000).toFixed(0), unit:"만원", color:"yellow", icon:"💰" },
          { lbl:"SLA 위반", val: kpiLoading ? "…" : (kpi?.sla_violations ?? 0), unit:"건", color:"red", icon:"⚠️" },
          { lbl:"평균 주문액", val: kpiLoading ? "…" : (kpi?.avg_order_value ?? 0).toLocaleString(), unit:"원", color:"blue", icon:"💳" },
          { lbl:"활성 점포", val: kpiLoading ? "…" : (kpi?.active_shops ?? 0), unit:"개", color:"green", icon:"🏪" },
        ].map(({ lbl, val, unit, color, icon }) => (
          <div key={lbl} className={`kpi ${color}`}>
            <div className="kpi-icon">{icon}</div>
            <div className="kpi-lbl">{lbl}</div>
            <div className="kpi-val">{val}<span style={{fontSize:12,fontWeight:400,marginLeft:3}}>{unit}</span></div>
          </div>
        ))}
      </div>

      <div className="g21">
        {/* 주간 정산 트렌드 */}
        <div className="card">
          <div className="card-title">
            주간 정산 트렌드
            <span style={{fontSize:10,color:"#888",fontWeight:400}}>최근 6건</span>
          </div>
          {settleList.length === 0 ? (
            <div style={{color:"#888",fontSize:12,padding:"20px 0",textAlign:"center"}}>정산 데이터가 없습니다</div>
          ) : (
            <div style={{overflowX:"auto"}}>
              <table className="tbl">
                <thead><tr>
                  <th>기간</th><th>점포</th><th>매출</th><th>수수료</th><th>정산액</th><th>상태</th>
                </tr></thead>
                <tbody>
                  {settleList.map((s, i) => (
                    <tr key={i}>
                      <td style={{fontSize:10,color:"#888"}}>{s.period_start} ~ {s.period_end}</td>
                      <td style={{fontWeight:600}}>{s.shop_name || "-"}</td>
                      <td>{(s.total_sales || 0).toLocaleString()}원</td>
                      <td style={{color:"var(--red)"}}>{(s.platform_fee || 0).toLocaleString()}원</td>
                      <td style={{fontWeight:700,color:"var(--blue)"}}>{(s.net_payout || 0).toLocaleString()}원</td>
                      <td><span className={`badge ${s.status === "PAID" ? "ab-green" : s.status === "PENDING" ? "ab-yellow" : "ab-gray"}`}>{s.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 오늘 주문 TOP 점포 */}
        <div className="card">
          <div className="card-title">점포별 오늘 주문 TOP 5</div>
          {shopsLoading ? <div style={{color:"#888",fontSize:12,textAlign:"center",padding:"20px 0"}}>로딩 중...</div> : (
            topShops.length === 0
              ? <div style={{color:"#888",fontSize:12,padding:"20px 0",textAlign:"center"}}>데이터 없음</div>
              : topShops.map((shop, i) => (
                <div key={shop.id} className="fn-row">
                  <div className="fn-lbl" style={{width:28,fontWeight:700,color:i===0?"var(--blue)":"#888"}}>#{i+1}</div>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{fontSize:11,fontWeight:600,marginBottom:2,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{shop.name}</div>
                    <div className="fn-bg">
                      <div className="fn-fill" style={{
                        width: `${Math.round((shop.today_orders / Math.max(...topShops.map(s => s.today_orders), 1)) * 100)}%`,
                        background: i===0 ? "var(--blue)" : i===1 ? "var(--green)" : "#AAB8FF",
                      }}>{shop.today_orders}건</div>
                    </div>
                  </div>
                  <div style={{fontSize:10,color:"#888"}}>{shop.rating?.toFixed(1)}★</div>
                </div>
              ))
          )}
        </div>
      </div>

      {/* SLA 위험 주문 */}
      <div className="card">
        <div className="card-title">
          SLA 위험 주문
          {slaRows.length > 0 && <span className="badge ab-red">{slaRows.length}건 위험</span>}
        </div>
        {slaLoading ? <div style={{color:"#888",fontSize:12,textAlign:"center",padding:"20px 0"}}>로딩 중...</div>
          : slaRows.length === 0
            ? <div style={{color:"var(--green)",fontSize:12,padding:"12px 0",textAlign:"center"}}>✅ SLA 위험 주문 없음</div>
            : (
              <table className="tbl">
                <thead><tr>
                  <th>주문번호</th><th>고객</th><th>점포</th><th>상태</th><th>마감까지</th>
                </tr></thead>
                <tbody>
                  {slaRows.map((o, i) => {
                    const h = typeof o.hours_left === "number" ? o.hours_left : null;
                    const urgent = h !== null && h < 1;
                    return (
                      <tr key={i}>
                        <td style={{fontFamily:"monospace",fontSize:11}}>{String(o.id || "").slice(-6).toUpperCase()}</td>
                        <td>{o.customer_name || "-"}</td>
                        <td>{o.shop_name || "-"}</td>
                        <td><span className="badge ab-yellow">{o.status}</span></td>
                        <td style={{fontWeight:700,color: urgent ? "var(--red)" : "var(--yellow)"}}>
                          {h !== null ? `${h.toFixed(1)}h` : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
      </div>
    </Layout>
  );
}

function SettingsPage() {
  return (
    <Layout title="시스템 설정"><style>{CSS}</style>
      <div className="g2">
        <div className="card">
          <div className="card-title">API 엔드포인트</div>
          {[["POST","/api/v1/orders","주문 생성"],["PATCH","/api/v1/orders/:id/status","상태 변경"],["GET","/api/v1/orders/partner/nearby","점포 매칭"],["GET","/api/v1/admin/settlements","정산 배치"],["GET","/api/v1/admin/dashboard","대시보드 KPI"],["WS","/ws/orders/:id","실시간 추적"]].map(([m,ep,desc],i)=>(
            <div key={i} style={{display:"flex",alignItems:"center",gap:8,padding:"7px 0",borderBottom:"1px solid #F8F8F8",fontSize:11}}>
              <span style={{fontFamily:"monospace",fontWeight:700,width:40,color:m==="GET"?"#00C853":m==="WS"?"#E65100":"#0057FF"}}>{m}</span>
              <span style={{fontFamily:"monospace",color:"#444",flex:1}}>{ep}</span>
              <span style={{color:"#888"}}>{desc}</span>
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-title">서비스 설정</div>
          {[["SLA 기준","12시간"],["Day 수거","09:00~"],["Night 수거","21:00~"],["정산 기준","매주 월요일"],["정산 지급","매출 +5일"],["수수료","건당 1,000원"]].map(([l,v],i)=>(
            <div key={i} style={{display:"flex",justifyContent:"space-between",padding:"8px 0",borderBottom:"1px solid #F8F8F8",fontSize:12}}>
              <span style={{color:"#888"}}>{l}</span><span style={{fontWeight:700}}>{v}</span>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  );
}

// ─── Route Switch & Root ──────────────────────────────────────────────────────
function RouteSwitch() {
  const { path } = useRouter();
  const map = {
    "/login":LoginPage, "/dashboard":Dashboard, "/orders":OrdersPage,
    "/shops":ShopsPage, "/settlements":SettlementsPage, "/marketing":MarketingPage,
    "/analytics":AnalyticsPage, "/settings":SettingsPage, "/logs":LogsPage,
  };
  const C = map[path] || LoginPage;
  return <C/>;
}

export default function AdminApp() {
  return (
    <Router>
      <AuthProvider>
        <RouteSwitch/>
      </AuthProvider>
    </Router>
  );
}
