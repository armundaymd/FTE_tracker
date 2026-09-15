import { useState, useMemo, useEffect, useRef, Fragment } from "react";
import PhysicianSearchSelect from "./PhysicianSearchSelect";

// ── Constants ──────────────────────────────────────────────────────────────
const LEAVE_TYPES = ["FMLA","LOA","Research Protected Time","Maternity/Paternity","Medical","Administrative","Other"];
const AUDIT_TABLES = ["physicians","site_assignments","physician_roles","sites","site_areas","leaves","monthly_demand"];
const AUDIT_ACTIONS = ["INSERT","UPDATE","DELETE"];

const YEAR = 2026;
const MONTHS_LIST = Array.from({ length: 12 }, (_, i) => ({
  key: `${YEAR}-${String(i+1).padStart(2,"0")}`, month: i+1,
  label: new Date(YEAR,i,1).toLocaleString("default",{month:"short"}),
  fullLabel: new Date(YEAR,i,1).toLocaleString("default",{month:"long"})+` ${YEAR}`,
}));

const LEAVE_COLORS = {"FMLA":{bg:"#FEE2E2",color:"#991B1B"},"LOA":{bg:"#F1F5F9",color:"#334155"},"Research Protected Time":{bg:"#DBEAFE",color:"#1E40AF"},"Maternity/Paternity":{bg:"#FCE7F3",color:"#831843"},"Medical":{bg:"#FEF3C7",color:"#92400E"},"Administrative":{bg:"#D1FAE5",color:"#065F46"},"Other":{bg:"#F1F5F9",color:"#334155"}};
const TYPE_COLORS = {"MD":{bg:"#EFF6FF",color:"#1D4ED8"},"DO":{bg:"#EFF6FF",color:"#1D4ED8"},"PA":{bg:"#F0FDF4",color:"#166534"},"NP":{bg:"#F0FDF4",color:"#166534"}};
const typeColor = (t) => TYPE_COLORS[t] || {bg:"#FEF9C3",color:"#854D0E"};

// ── API ────────────────────────────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "https://api-capacity.adamrmunday.com/api";

// Access token lives only in memory (never localStorage). It's set by App
// from React state on login/logout/refresh; mirrored here so the plain
// apiFetch() helper below — called from every tab without prop-drilling a
// token — always has the current value.
let accessToken = null;
let onAuthExpired = null; // App registers this to drop back to the login screen

function setApiAuthToken(token) { accessToken = token; }
function setOnAuthExpired(handler) { onAuthExpired = handler; }

async function refreshAccessToken() {
  const res = await fetch(`${API_BASE}/auth/refresh`, { method: "POST", credentials: "include" });
  if (!res.ok) return null;
  const data = await res.json();
  return data.access_token;
}

async function apiFetch(path, opts = {}, _isRetry = false) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include", // sends the httpOnly refresh-token cookie
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    ...opts,
  });

  if (res.status === 401 && accessToken && !_isRetry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      accessToken = newToken;
      return apiFetch(path, opts, true); // retry the original request once
    }
    accessToken = null;
    onAuthExpired?.();
    throw new Error("Your session expired — please log in again.");
  }

  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed: ${res.status}`);
  return data;
}

// ── CSS ────────────────────────────────────────────────────────────────────
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
:root{
  --bg:#F0F4F8;--surface:#FFFFFF;--surface2:#F8FAFC;
  --border:#E2E8F0;--border2:#CBD5E1;
  --sidebar:#0F172A;--text:#0F172A;--muted:#64748B;--faint:#94A3B8;
  --accent:#0891B2;--accent-bg:#E0F2FE;
  --green:#059669;--green-bg:#D1FAE5;
  --red:#DC2626;--red-bg:#FEE2E2;
  --r:8px;--rl:12px;
  --shadow:0 1px 3px rgba(0,0,0,.07),0 1px 2px rgba(0,0,0,.04);
}
body,html{height:100%;font-family:'DM Sans',system-ui,sans-serif;background:var(--bg);color:var(--text);}
#root{height:100%;}
.shell{display:flex;height:100vh;overflow:hidden;}
.sidebar{width:220px;min-width:220px;background:var(--sidebar);display:flex;flex-direction:column;overflow-y:auto;}
.sb-logo{padding:22px 18px 18px;border-bottom:1px solid rgba(255,255,255,.07);}
.sb-logo .tag{font-size:10px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:#38BDF8;margin-bottom:5px;}
.sb-logo .name{font-size:15px;font-weight:600;color:#F1F5F9;line-height:1.25;}
.sb-logo .sub{font-size:11px;color:#64748B;margin-top:3px;}
.sb-nav{padding:14px 10px;display:flex;flex-direction:column;gap:2px;}
.sb-item{display:flex;align-items:center;gap:10px;padding:9px 11px;border-radius:6px;font-size:13px;font-weight:500;color:#94A3B8;cursor:pointer;border:none;background:none;width:100%;text-align:left;transition:background .12s,color .12s;}
.sb-item:hover{background:rgba(255,255,255,.06);color:#E2E8F0;}
.sb-item.active{background:rgba(14,165,233,.18);color:#38BDF8;}
.sb-item svg{width:15px;height:15px;flex-shrink:0;opacity:.75;}
.sb-item.active svg{opacity:1;}
.sb-badge{margin-left:auto;background:rgba(14,165,233,.22);color:#38BDF8;font-size:10px;font-weight:700;padding:1px 7px;border-radius:10px;}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:0 28px;height:54px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;}
.topbar .title{font-size:15px;font-weight:600;color:var(--text);}
.topbar .sub{font-size:11px;color:var(--muted);margin-top:1px;}
.year-chip{background:var(--accent-bg);color:var(--accent);font-size:12px;font-weight:600;padding:4px 14px;border-radius:20px;}
.content{flex:1;overflow-y:auto;padding:24px 28px;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--rl);padding:20px 22px;margin-bottom:16px;box-shadow:var(--shadow);}
.card-title{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:16px;}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:var(--rl);padding:16px 18px;box-shadow:var(--shadow);}
.kpi-label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:8px;}
.kpi-value{font-size:26px;font-weight:600;color:var(--text);line-height:1;font-family:'DM Mono',monospace;}
.kpi-sub{font-size:11px;color:var(--muted);margin-top:5px;}
.kpi.red .kpi-value{color:var(--red);}
.kpi.green .kpi-value{color:var(--green);}
.seg{display:inline-flex;background:var(--surface2);border:1px solid var(--border);border-radius:var(--r);padding:3px;gap:2px;margin-bottom:16px;}
.seg-btn{padding:5px 14px;font-size:12px;font-weight:500;font-family:inherit;border:none;border-radius:5px;background:none;color:var(--muted);cursor:pointer;transition:all .12s;}
.seg-btn.active{background:var(--surface);color:var(--text);box-shadow:0 1px 3px rgba(0,0,0,.1);}
.tbl-wrap{overflow-x:auto;}
table.tbl{width:100%;border-collapse:collapse;font-size:13px;}
table.tbl thead tr{border-bottom:1px solid var(--border);}
table.tbl thead th{text-align:left;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);padding:9px 12px;white-space:nowrap;}
table.tbl thead th.r{text-align:right;}
table.tbl tbody td{padding:9px 12px;border-bottom:1px solid var(--border);color:var(--text);vertical-align:middle;}
table.tbl tbody td.r{text-align:right;}
table.tbl tbody td.mono{font-family:'DM Mono',monospace;font-size:12px;}
table.tbl tbody td.bold{font-weight:600;}
table.tbl tbody td.muted{color:var(--muted);font-size:12px;}
table.tbl tbody tr:last-child td{border-bottom:none;}
table.tbl tbody tr:hover td{background:#FAFBFC;}
.pos{color:var(--green);font-weight:600;font-family:'DM Mono',monospace;font-size:12px;}
.neg{color:var(--red);font-weight:600;font-family:'DM Mono',monospace;font-size:12px;}
.neu{color:var(--faint);font-family:'DM Mono',monospace;font-size:12px;}
.form-row{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;}
.field{display:flex;flex-direction:column;gap:5px;}
.field label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);}
.field input,.field select,.field textarea{height:36px;padding:0 10px;font-size:13px;font-family:inherit;border:1px solid var(--border2);border-radius:var(--r);background:var(--surface);color:var(--text);outline:none;transition:border-color .15s,box-shadow .15s;}
.field textarea{height:60px;padding:8px 10px;resize:vertical;}
.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(8,145,178,.12);}
.field input[type=text]{min-width:160px;}
.field input[type=number]{width:90px;}
.field input[type=date]{width:152px;}
.btn{height:36px;padding:0 16px;font-size:13px;font-weight:500;font-family:inherit;border:1px solid var(--border2);border-radius:var(--r);background:var(--surface);color:var(--text);cursor:pointer;display:inline-flex;align-items:center;gap:6px;transition:all .12s;white-space:nowrap;}
.btn:hover{background:var(--surface2);}
.btn:active{transform:scale(.98);}
.btn:disabled{opacity:.5;cursor:not-allowed;}
.btn.primary{background:var(--accent);color:#fff;border-color:var(--accent);}
.btn.primary:hover{background:#0e7490;border-color:#0e7490;}
.btn.danger{color:var(--red);border-color:#FECACA;}
.btn.danger:hover{background:var(--red-bg);}
.btn.sm{height:30px;padding:0 10px;font-size:12px;}
.lbadge{display:inline-flex;align-items:center;padding:2px 9px;border-radius:20px;font-size:11px;font-weight:600;}
.stag{display:inline-flex;align-items:center;background:var(--accent-bg);color:var(--accent);border-radius:4px;padding:2px 7px;font-size:11px;font-weight:600;margin-right:3px;margin-bottom:2px;}
.rtag{display:inline-flex;align-items:center;background:#F1F5F9;color:#475569;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:500;margin-right:3px;margin-bottom:2px;}
.demand-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;}
.demand-cell label{display:flex;justify-content:space-between;align-items:baseline;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:4px;}
.demand-status{font-size:9px;font-weight:600;text-transform:none;letter-spacing:0;}
.demand-status.saving{color:var(--accent);}
.demand-status.saved{color:var(--green);}
.demand-status.error{color:var(--red);}
.demand-cell input{width:100%;height:32px;padding:0 6px;font-size:13px;font-family:'DM Mono',monospace;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--text);text-align:center;outline:none;}
.demand-cell input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(8,145,178,.12);}
.demand-cell input.input-error{border-color:var(--red);}
.assign-row{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border);}
.assign-row:last-of-type{border-bottom:none;}
.assign-row select,.assign-row input{height:30px;padding:0 8px;font-size:12px;font-family:inherit;border:1px solid var(--border2);border-radius:var(--r);background:var(--surface);color:var(--text);outline:none;}
.assign-row select{min-width:100px;}
.assign-row input{width:80px;font-family:'DM Mono',monospace;text-align:center;}
.role-row{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);}
.role-row:last-of-type{border-bottom:none;}
.role-row select,.role-row input{height:30px;padding:0 8px;font-size:12px;font-family:inherit;border:1px solid var(--border2);border-radius:var(--r);background:var(--surface);color:var(--text);outline:none;}
.legend{display:flex;gap:16px;margin-bottom:12px;}
.legend-item{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--muted);}
.legend-dot{width:8px;height:8px;border-radius:50%;}
.empty{text-align:center;padding:32px;color:var(--muted);font-size:13px;}
.divider{height:1px;background:var(--border);margin:16px 0;}
.sub-section{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-bottom:10px;margin-top:16px;}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.info-box{background:var(--accent-bg);border:1px solid #BAE6FD;border-radius:var(--r);padding:12px 14px;font-size:12px;color:#0369A1;margin-bottom:16px;line-height:1.5;}
.err-banner{background:#FEE2E2;border:1px solid #FECACA;border-radius:var(--r);padding:12px 16px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;color:var(--red);font-size:13px;}
@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
.spin{animation:spin .8s linear infinite}
.login-page{height:100vh;display:flex;align-items:center;justify-content:center;background:var(--sidebar);}
.login-card{width:340px;background:var(--surface);border-radius:var(--rl);padding:32px 30px;box-shadow:0 10px 40px rgba(0,0,0,.25);}
.login-tag{font-size:10px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:5px;}
.login-title{font-size:17px;font-weight:600;color:var(--text);margin-bottom:22px;}
.login-field{display:flex;flex-direction:column;gap:5px;margin-bottom:14px;}
.login-field label{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);}
.login-field input{height:38px;padding:0 11px;font-size:13px;font-family:inherit;border:1px solid var(--border2);border-radius:var(--r);background:var(--surface);color:var(--text);outline:none;transition:border-color .15s,box-shadow .15s;}
.login-field input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(8,145,178,.12);}
.login-error{background:var(--red-bg);border:1px solid #FECACA;border-radius:var(--r);padding:9px 12px;font-size:12px;color:var(--red);margin-bottom:14px;}
.login-btn{width:100%;height:38px;margin-top:6px;}
.user-chip{display:flex;flex-direction:column;align-items:flex-end;line-height:1.3;}
.user-chip .u-name{font-size:12px;font-weight:600;color:var(--text);}
.user-chip .u-email{font-size:11px;color:var(--muted);}
.audit-summary{font-size:12px;color:var(--muted);font-family:'DM Mono',monospace;}
.audit-summary b{color:var(--text);font-weight:600;font-family:inherit;}
.timeline{display:flex;flex-direction:column;}
.timeline-item{position:relative;display:flex;gap:12px;padding-bottom:18px;}
.timeline-item:last-child{padding-bottom:0;}
.timeline-marker{position:relative;display:flex;flex-direction:column;align-items:center;width:9px;flex-shrink:0;}
.timeline-dot{width:9px;height:9px;border-radius:50%;margin-top:4px;flex-shrink:0;}
.timeline-line{flex:1;width:1px;background:var(--border);margin-top:4px;}
.timeline-body{flex:1;padding-bottom:2px;}
.timeline-date{font-size:11px;color:var(--muted);font-family:'DM Mono',monospace;margin-bottom:2px;}
.timeline-desc{font-size:13px;color:var(--text);font-weight:500;}
.timeline-reason{font-size:12px;color:var(--muted);font-style:italic;margin-top:3px;}
.psearch{position:relative;}
.psearch-dropdown{position:absolute;top:calc(100% + 4px);left:0;right:0;z-index:20;background:var(--surface);border:1px solid var(--border2);border-radius:var(--r);box-shadow:0 4px 16px rgba(0,0,0,.14);max-height:220px;overflow-y:auto;}
.psearch-option{padding:8px 11px;font-size:13px;color:var(--text);cursor:pointer;}
.psearch-option.active{background:var(--accent-bg);color:var(--accent);}
.psearch-option.selected{font-weight:600;}
.psearch-empty{padding:10px 11px;font-size:12px;color:var(--muted);}
.talloc-input{width:100%;min-width:46px;height:30px;padding:0 4px;font-size:12px;font-family:'DM Mono',monospace;text-align:center;border:1px solid var(--border);border-radius:var(--r);background:var(--surface);color:var(--text);outline:none;transition:border-color .15s,box-shadow .15s;}
.talloc-input:focus{border-color:var(--accent);box-shadow:0 0 0 2px rgba(8,145,178,.12);}
.talloc-input.changed{border-color:var(--accent);background:var(--accent-bg);}
.talloc-section-row td{background:var(--surface2);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);padding:8px 12px;}
.talloc-needs-row{display:flex;align-items:center;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--border);}
.talloc-needs-row:last-child{border-bottom:none;}
`;

// ── Icons ──────────────────────────────────────────────────────────────────
const Ico = ({d,s=15}) => <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={d}/></svg>;
const IcoDash  = () => <Ico d="M3 12h4M3 6h8M3 18h6M17 3v18M21 7l-4 4-4-4"/>;
const IcoUsers = () => <Ico d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>;
const IcoSite  = () => <Ico d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10"/>;
const IcoChart = () => <Ico d="M18 20V10M12 20V4M6 20v-6"/>;
const IcoLeave = () => <Ico d="M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM10 16l2 2 4-4"/>;
const IcoTrash = () => <Ico d="M3 6h18M8 6V4h8v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" s={13}/>;
const IcoPlus  = () => <Ico d="M12 5v14M5 12h14" s={13}/>;
const IcoEdit  = () => <Ico d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" s={13}/>;
const IcoStaff = () => <Ico d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2M9 5a2 2 0 0 0 2-2h2a2 2 0 0 0 2 2m-3 7h.01M9 17h6M9 13h6"/>;
const IcoAudit = () => <Ico d="M9 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4M9 3h6a2 2 0 0 1 2 2v4M9 3v4a2 2 0 0 0 2 2h6M9 15h4M9 11h2M17 15l2 2 4-4"/>;
const IcoGrid  = () => <Ico d="M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z"/>;

// ── Small components ───────────────────────────────────────────────────────
const LeaveBadge = ({type}) => { const c=LEAVE_COLORS[type]||LEAVE_COLORS.Other; return <span className="lbadge" style={{background:c.bg,color:c.color}}>{type}</span>; };
const TypeBadge  = ({type}) => { const c=typeColor(type); return <span className="lbadge" style={{background:c.bg,color:c.color}}>{type}</span>; };
const Gap = ({val,unit=""}) => { if(val===0) return <span className="neu">0{unit}</span>; return <span className={val>0?"pos":"neg"}>{val>0?"+":""}{val}{unit}</span>; };
const ACTION_COLORS = {INSERT:{bg:"var(--green-bg)",color:"var(--green)"},UPDATE:{bg:"var(--accent-bg)",color:"var(--accent)"},DELETE:{bg:"var(--red-bg)",color:"var(--red)"}};
const ActionBadge = ({action}) => { const c=ACTION_COLORS[action]||{bg:"#F1F5F9",color:"#475569"}; return <span className="lbadge" style={{background:c.bg,color:c.color}}>{action}</span>; };

function Spinner() {
  return (
    <div style={{display:"flex",alignItems:"center",justifyContent:"center",padding:"60px",color:"var(--muted)"}}>
      <svg className="spin" width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
      </svg>
    </div>
  );
}

function LoginScreen({onLogin}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await onLogin(email, password);
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-tag">Emergency Medicine</div>
        <div className="login-title">Sign in to Capacity Planner</div>
        {error && <div className="login-error">{error}</div>}
        <div className="login-field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e)=>setEmail(e.target.value)} autoComplete="username" required autoFocus/>
        </div>
        <div className="login-field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e)=>setPassword(e.target.value)} autoComplete="current-password" required/>
        </div>
        <button type="submit" className="btn primary login-btn" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

function ErrorBanner({message, onDismiss}) {
  if (!message) return null;
  return (
    <div className="err-banner">
      <span>{message}</span>
      <button onClick={onDismiss} style={{background:"none",border:"none",cursor:"pointer",color:"var(--red)",fontWeight:700,fontSize:18,lineHeight:1,marginLeft:12}}>×</button>
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────
function Dashboard({sites, physicians, leaves, capacity}) {
  const [view, setView] = useState("all");

  const rows = capacity?.rows || [];

  const totals = useMemo(() => MONTHS_LIST.map(({key, month, fullLabel}) => {
    const mr = rows.filter(r => r.month === month);
    const aH    = mr.reduce((s,r) => s + r.available_hours, 0);
    const rH    = mr.reduce((s,r) => s + r.required_hours, 0);
    const aFTE  = mr.reduce((s,r) => s + r.available_fte, 0);
    const rFTE  = mr.reduce((s,r) => s + r.required_fte, 0);
    const aCliH  = mr.reduce((s,r) => s + r.clinical_hours, 0);
    return {
      key, fullLabel,
      aH: Math.round(aH), rH: Math.round(rH), hGap: Math.round(aH - rH),
      aFTE: Math.round(aFTE*10)/10, rFTE: Math.round(rFTE*10)/10, fteGap: Math.round((aFTE-rFTE)*10)/10,
      aCliH: Math.round(aCliH),
    };
  }), [rows]);

  const deficitMonths = totals.filter(t => t.hGap < 0).length;
  const peakDeficit   = Math.min(0, ...totals.map(t => t.hGap));
  const peakSurplus   = Math.max(0, ...totals.map(t => t.hGap));

  const curMonth = new Date().getMonth() + 1;
  const onLeaveNow = physicians.filter(p =>
    leaves.some(l => {
      if (l.physician_id !== p.id) return false;
      const dim = new Date(YEAR, curMonth, 0).getDate();
      const ms = new Date(YEAR, curMonth-1, 1);
      const me = new Date(YEAR, curMonth-1, dim);
      const ls = new Date(l.start_date + "T00:00:00");
      const le = new Date(l.end_date   + "T00:00:00");
      return !(ls > me || le < ms);
    })
  ).length;

  const DataTable = ({rows: tableRows}) => (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead><tr>
          <th>Month</th>
          <th className="r">Avail hrs</th><th className="r">Clin hrs</th>
          <th className="r">Req hrs</th><th className="r">Hours gap</th>
          <th className="r">Avail FTE</th><th className="r">Req FTE</th><th className="r">FTE gap</th>
        </tr></thead>
        <tbody>
          {tableRows.map(r=>(
            <tr key={r.key}>
              <td className="bold">{r.fullLabel||r.key}</td>
              <td className="r mono">{r.aH}</td>
              <td className="r mono" style={{color:"var(--green)"}}>{r.aCliH}</td>
              <td className="r mono">{r.rH}</td>
              <td className="r"><Gap val={r.hGap} unit=" hrs"/></td>
              <td className="r mono">{r.aFTE}</td>
              <td className="r mono">{r.rFTE}</td>
              <td className="r"><Gap val={r.fteGap}/></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const mdCount     = physicians.filter(p => ["MD","DO"].includes(p.provider_type?.name||"")).length;
  const appCount    = physicians.filter(p => ["PA","NP"].includes(p.provider_type?.name||"")).length;
  const fellowCount = physicians.filter(p => (p.provider_type?.name||"").startsWith("Fellow")).length;

  return (
    <div>
      <div className="kpi-grid">
        <div className="kpi">
          <div className="kpi-label">Providers</div>
          <div className="kpi-value">{physicians.length}</div>
          <div className="kpi-sub">{mdCount} MD/DO · {appCount} APP · {fellowCount} Fellow</div>
        </div>
        <div className={`kpi ${onLeaveNow>0?"red":""}`}>
          <div className="kpi-label">On leave now</div>
          <div className="kpi-value">{onLeaveNow}</div>
          <div className="kpi-sub">{leaves.length} leave events total</div>
        </div>
        <div className={`kpi ${deficitMonths>0?"red":"green"}`}>
          <div className="kpi-label">Deficit months</div>
          <div className="kpi-value">{deficitMonths}</div>
          <div className="kpi-sub">of 12 months in {YEAR}</div>
        </div>
        <div className={`kpi ${peakDeficit<0?"red":"green"}`}>
          <div className="kpi-label">Peak gap</div>
          <div className="kpi-value">{peakDeficit<0?peakDeficit:"+"+peakSurplus}</div>
          <div className="kpi-sub">hours in worst month</div>
        </div>
      </div>

      <div className="seg">
        <button className={`seg-btn ${view==="all"?"active":""}`} onClick={()=>setView("all")}>All sites combined</button>
        <button className={`seg-btn ${view==="site"?"active":""}`} onClick={()=>setView("site")}>By site</button>
      </div>

      {view==="all" && (
        <div className="card">
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:12}}>
            <div className="card-title" style={{margin:0}}>Monthly capacity — all sites</div>
            <div className="legend" style={{margin:0}}>
              <div className="legend-item"><div className="legend-dot" style={{background:"#059669"}}></div>Surplus</div>
              <div className="legend-item"><div className="legend-dot" style={{background:"#DC2626"}}></div>Deficit</div>
            </div>
          </div>
          <DataTable rows={totals}/>
        </div>
      )}

      {view==="site" && sites.map(site => {
        const siteRows = MONTHS_LIST.map(({key, fullLabel, month}) => {
          const row = rows.find(r => r.site_id === site.id && r.month === month);
          return {
            key, fullLabel,
            aH: row?.available_hours ?? 0, rH: row?.required_hours ?? 0, hGap: row?.hours_gap ?? 0,
            aFTE: row?.available_fte ?? 0, rFTE: row?.required_fte ?? 0, fteGap: row?.fte_gap ?? 0,
            aCliH: row?.clinical_hours ?? 0,
          };
        });
        return (
          <div key={site.id} className="card">
            <div className="card-title">{site.name}</div>
            <DataTable rows={siteRows}/>
          </div>
        );
      })}
    </div>
  );
}

// ── Physicians ─────────────────────────────────────────────────────────────
function PhysiciansTab({sites, lookupTables, onRefresh, onError}) {
  const [adding,    setAdding]    = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editingOriginal, setEditingOriginal] = useState(null);

  // ── Self-fetched, server-filtered roster ──────────────────────────────────
  const [rows,        setRows]        = useState([]);
  const [totalCount,  setTotalCount]  = useState(0);
  const [loadingRows, setLoadingRows] = useState(true);

  const [siteFilter,   setSiteFilter]   = useState("");
  const [typeFilter,   setTypeFilter]   = useState("");
  const [statusFilter, setStatusFilter] = useState("Active");   // All | Active | Inactive
  const [coreFilter,   setCoreFilter]   = useState("All");      // All | Core | Non-core
  const [needsFteOnly, setNeedsFteOnly] = useState(false);

  const hasFilters = Boolean(siteFilter || typeFilter || statusFilter!=="Active" || coreFilter!=="All" || needsFteOnly);
  const clearFilters = () => {
    setSiteFilter(""); setTypeFilter(""); setStatusFilter("Active"); setCoreFilter("All"); setNeedsFteOnly(false);
  };

  const loadRows = async () => {
    setLoadingRows(true);
    try {
      const params = new URLSearchParams();
      if (siteFilter) params.set("site_id", siteFilter);
      if (typeFilter) params.set("provider_type_id", typeFilter);
      if (statusFilter==="Active") params.set("is_active", "true");
      else if (statusFilter==="Inactive") params.set("is_active", "false");
      if (coreFilter==="Core") params.set("is_core_faculty", "true");
      else if (coreFilter==="Non-core") params.set("is_core_faculty", "false");
      if (needsFteOnly) params.set("needs_fte_config", "true");
      const data = await apiFetch(`/physicians/?${params.toString()}`);
      setRows(data);
    } catch (err) {
      onError(err.message);
    } finally {
      setLoadingRows(false);
    }
  };

  const loadTotal = async () => {
    try {
      const data = await apiFetch("/physicians/"); // unfiltered — grand total, active + inactive
      setTotalCount(data.length);
    } catch (err) {
      onError(err.message);
    }
  };

  useEffect(() => { loadRows(); }, [siteFilter, typeFilter, statusFilter, coreFilter, needsFteOnly]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { loadTotal(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshAll = async () => {
    await Promise.all([loadRows(), loadTotal(), onRefresh()]);
  };

  const blankForm = {
    life_no: "", last_name: "", first_name: "",
    provider_type_id: null, yearly_hours: 1440, clinical_pct: 1.0,
    core_site_id: null, notes: "", assignments: [], roles: [],
  };
  const [form, setForm] = useState(blankForm);

  const startEdit = (p) => {
    setEditingId(p.id);
    setEditingOriginal(p);
    setForm({
      life_no: p.life_no||"", last_name: p.last_name, first_name: p.first_name,
      provider_type_id: p.provider_type_id, yearly_hours: p.yearly_hours, clinical_pct: p.clinical_pct,
      core_site_id: p.core_site_id, notes: p.notes||"",
      // Only currently-open rows are editable here — closed/historical rows
      // (Phase B's FTE history) show up in the History timeline below instead.
      assignments: p.assignments.filter(a=>!a.end_date).map(a=>({id: a.id, site_id: a.site_id, fte_fraction: a.fte_fraction, change_reason: ""})),
      roles: p.roles.filter(r=>!r.end_date).map(r=>({id: r.id, role_type_id: r.role_type_id, hours_credit: r.hours_credit, change_reason: ""})),
    });
    setAdding(true);
  };

  const cancelForm = () => {
    setAdding(false);
    setEditingId(null);
    setEditingOriginal(null);
    setForm(blankForm);
  };

  const onTypeChange = (val) => {
    const id = val ? parseInt(val) : null;
    const pt = lookupTables.provider_types.find(t => t.id === id);
    setForm(f => ({...f, provider_type_id: id, yearly_hours: pt?.default_fte_hours || 1440}));
  };

  const addAssign = () => {
    if (!sites.length) return;
    setForm(f => ({...f, assignments: [...f.assignments, {site_id: sites[0].id, fte_fraction: 0.5}]}));
  };
  const updAssign = (i, field, val) => setForm(f => {
    const a = [...f.assignments];
    a[i] = {...a[i], [field]: field === "fte_fraction" ? parseFloat(val) || 0 : val};
    return {...f, assignments: a};
  });
  const rmAssign = (i) => setForm(f => ({...f, assignments: f.assignments.filter((_,j) => j !== i)}));

  const addRole = () => {
    const first = lookupTables.role_types[0];
    setForm(f => ({...f, roles: [...f.roles, {role_type_id: first?.id || null, hours_credit: 0}]}));
  };
  const updRole = (i, field, val) => setForm(f => {
    const r = [...f.roles];
    r[i] = {...r[i], [field]: field === "hours_credit" ? parseInt(val) || 0 : field === "role_type_id" ? (val ? parseInt(val) : null) : val};
    return {...f, roles: r};
  });
  const rmRole = (i) => setForm(f => ({...f, roles: f.roles.filter((_,j) => j !== i)}));

  // Applies edits to an existing physician's assignments/roles by diffing
  // against the original — the API only exposes per-row POST/PUT/DELETE for
  // these sub-resources, there's no bulk "replace all" endpoint.
  const syncAssignments = async (physicianId, original, current) => {
    const currentIds = new Set(current.filter(a=>a.id).map(a=>a.id));
    for (const a of original.filter(a=>!currentIds.has(a.id))) {
      await apiFetch(`/physicians/${physicianId}/assignments/${a.id}`, {method: "DELETE"});
    }
    for (const a of current.filter(a=>a.id)) {
      const body = {site_id: a.site_id, fte_fraction: a.fte_fraction};
      if (a.change_reason) body.change_reason = a.change_reason;
      await apiFetch(`/physicians/${physicianId}/assignments/${a.id}`, {method: "PUT", body: JSON.stringify(body)});
    }
    for (const a of current.filter(a=>!a.id)) {
      await apiFetch(`/physicians/${physicianId}/assignments`, {
        method: "POST", body: JSON.stringify({site_id: a.site_id, fte_fraction: a.fte_fraction}),
      });
    }
  };

  // Existing rows go through PUT — the API closes-and-inserts a new history
  // row when hours_credit/pct_credit actually changes, so this is also what
  // carries change_reason into that history.
  const syncRoles = async (physicianId, original, current) => {
    const currentIds = new Set(current.filter(r=>r.id).map(r=>r.id));
    for (const r of original.filter(r=>!currentIds.has(r.id))) {
      await apiFetch(`/physicians/${physicianId}/roles/${r.id}`, {method: "DELETE"});
    }
    for (const r of current.filter(r=>r.id)) {
      const body = {role_type_id: r.role_type_id, hours_credit: r.hours_credit};
      if (r.change_reason) body.change_reason = r.change_reason;
      await apiFetch(`/physicians/${physicianId}/roles/${r.id}`, {method: "PUT", body: JSON.stringify(body)});
    }
    for (const r of current.filter(r=>!r.id)) {
      await apiFetch(`/physicians/${physicianId}/roles`, {
        method: "POST", body: JSON.stringify({role_type_id: r.role_type_id, hours_credit: r.hours_credit}),
      });
    }
  };

  const save = async () => {
    if (!form.last_name.trim()) {
      onError("Last name is required.");
      return;
    }
    if (!editingId && !form.assignments.length) {
      onError("Add at least one site assignment before saving a new provider.");
      return;
    }
    setSaving(true);
    try {
      const body = {
        ...form,
        // life_no is unique in the DB — "" (unlike NULL) collides once a
        // second provider also has a blank one, so send null instead.
        life_no: form.life_no.trim() || null,
        yearly_hours: parseInt(form.yearly_hours) || 1440,
        clinical_pct: parseFloat(form.clinical_pct) || 1.0,
        core_site_id: form.core_site_id || null,
      };
      if (editingId) {
        await apiFetch(`/physicians/${editingId}`, {
          method: "PUT",
          body: JSON.stringify({
            life_no: body.life_no, last_name: body.last_name, first_name: body.first_name,
            provider_type_id: body.provider_type_id, yearly_hours: body.yearly_hours,
            clinical_pct: body.clinical_pct, core_site_id: body.core_site_id, notes: body.notes,
          }),
        });
        await syncAssignments(editingId, editingOriginal.assignments, form.assignments);
        await syncRoles(editingId, editingOriginal.roles, form.roles);
      } else {
        await apiFetch("/physicians/", {method: "POST", body: JSON.stringify(body)});
      }
      cancelForm();
      await refreshAll();
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const deletePhysician = async (id) => {
    try {
      await apiFetch(`/physicians/${id}`, {method: "DELETE"});
      await refreshAll();
    } catch (err) {
      onError(err.message);
    }
  };

  // Scaled by total_fte (actual site-assignment deployment), not just
  // yearly_hours x clinical_pct — matches the Excel's cFTE formula
  // (Clinical hours / yearly_hours) x site FTE. A physician with no site
  // assignments (total_fte = 0) correctly shows 0 clinical hours here,
  // even if clinical_pct is configured, since they aren't actually
  // deployed anywhere yet.
  const clinHrs = p => Math.round(p.yearly_hours * parseFloat(p.clinical_pct || 0) * parseFloat(p.total_fte || 0));
  // Only currently-open roles count toward active credit hours — closed
  // (historical) rows would otherwise double-count past and present credit.
  const roleHrs = p => p.roles.filter(r=>!r.end_date).reduce((s, r) => s + (r.hours_credit || 0), 0);

  return (
    <div>
      {!adding && (
        <div style={{marginBottom:16}}>
          <button className="btn primary" onClick={()=>setAdding(true)}><IcoPlus/> Add provider</button>
        </div>
      )}

      {!adding && (
        <div className="card">
          <div className="card-title">Filters</div>
          <div className="form-row">
            <div className="field"><label>Site</label>
              <select value={siteFilter} onChange={e=>setSiteFilter(e.target.value)} style={{minWidth:150}}>
                <option value="">All sites</option>
                {sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div className="field"><label>Provider type</label>
              <select value={typeFilter} onChange={e=>setTypeFilter(e.target.value)} style={{minWidth:160}}>
                <option value="">All types</option>
                {lookupTables.provider_types.map(t=><option key={t.id} value={String(t.id)}>{t.name}</option>)}
              </select>
            </div>
            <div className="field"><label>Status</label>
              <select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} style={{minWidth:110}}>
                <option value="All">All</option>
                <option value="Active">Active</option>
                <option value="Inactive">Inactive</option>
              </select>
            </div>
            <div className="field"><label>Core faculty</label>
              <select value={coreFilter} onChange={e=>setCoreFilter(e.target.value)} style={{minWidth:110}}>
                <option value="All">All</option>
                <option value="Core">Core</option>
                <option value="Non-core">Non-core</option>
              </select>
            </div>
            <div className="field">
              <label>&nbsp;</label>
              <label style={{display:"flex",alignItems:"center",gap:6,height:36,fontSize:13,color:"var(--text)",cursor:"pointer"}}>
                <input type="checkbox" checked={needsFteOnly} onChange={e=>setNeedsFteOnly(e.target.checked)}/>
                Needs FTE config
              </label>
            </div>
            {hasFilters && <button className="btn" onClick={clearFilters}>Clear filters</button>}
          </div>
        </div>
      )}

      {adding && (
        <div className="card">
          <div className="card-title">{editingId ? "Edit provider" : "New provider"}</div>
          <div className="form-row" style={{marginBottom:14}}>
            <div className="field"><label>Life No</label><input type="text" style={{width:100}} value={form.life_no} onChange={e=>setForm(f=>({...f,life_no:e.target.value}))} placeholder="10001"/></div>
            <div className="field"><label>Last name</label><input type="text" value={form.last_name} onChange={e=>setForm(f=>({...f,last_name:e.target.value}))} placeholder="Smith"/></div>
            <div className="field"><label>First name</label><input type="text" value={form.first_name} onChange={e=>setForm(f=>({...f,first_name:e.target.value}))} placeholder="Jane"/></div>
            <div className="field"><label>Type</label>
              <select value={String(form.provider_type_id||"")} onChange={e=>onTypeChange(e.target.value)} style={{minWidth:160}}>
                <option value="">Select type…</option>
                {lookupTables.provider_types.map(t=><option key={t.id} value={String(t.id)}>{t.name}</option>)}
              </select>
            </div>
          </div>
          <div className="form-row" style={{marginBottom:14}}>
            <div className="field"><label>1.0 FTE hours/yr</label><input type="number" min={0} value={form.yearly_hours} onChange={e=>setForm(f=>({...f,yearly_hours:e.target.value}))}/></div>
            <div className="field"><label>Clinical %</label><input type="number" step="0.05" min={0} max={1} style={{width:90}} value={form.clinical_pct} onChange={e=>setForm(f=>({...f,clinical_pct:e.target.value}))} placeholder="0.80"/></div>
            <div className="field"><label>Core site</label>
              <select value={form.core_site_id||""} onChange={e=>setForm(f=>({...f,core_site_id:e.target.value||null}))} style={{minWidth:120}}>
                <option value="">None</option>
                {sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>
          <div className="field" style={{marginBottom:14}}>
            <label>Notes</label>
            <textarea value={form.notes} onChange={e=>setForm(f=>({...f,notes:e.target.value}))} placeholder="Splits, grants, LOAs, special arrangements..."/>
          </div>

          <div className="divider"/>
          <div className="sub-section">Administrative roles (hour credits)</div>
          {form.roles.length===0 && <div style={{fontSize:12,color:"var(--faint)",marginBottom:8}}>No roles — add below if applicable.</div>}
          {form.roles.map((r,i)=>(
            <div key={i} className="role-row">
              <select value={String(r.role_type_id||"")} style={{minWidth:200}} onChange={e=>updRole(i,"role_type_id",e.target.value)}>
                <option value="">Select role…</option>
                {lookupTables.role_types.map(t=><option key={t.id} value={String(t.id)}>{t.name}</option>)}
              </select>
              <span style={{fontSize:12,color:"var(--muted)"}}>hours credit</span>
              <input type="number" min={0} value={r.hours_credit} onChange={e=>updRole(i,"hours_credit",e.target.value)}/>
              {r.id && (
                <input
                  type="text"
                  placeholder="Reason for change (optional)"
                  value={r.change_reason||""}
                  onChange={e=>updRole(i,"change_reason",e.target.value)}
                  style={{width:220,fontFamily:"inherit",textAlign:"left"}}
                />
              )}
              <button className="btn sm danger" onClick={()=>rmRole(i)}><IcoTrash/></button>
            </div>
          ))}
          <button className="btn sm" style={{marginTop:8}} onClick={addRole}><IcoPlus/> Add role</button>

          <div className="divider"/>
          <div className="sub-section">Site assignments</div>
          {form.assignments.length===0 && <div style={{fontSize:12,color:"var(--faint)",marginBottom:8}}>No sites assigned.</div>}
          {form.assignments.map((a,i)=>(
            <div key={i} className="assign-row">
              <select value={a.site_id||""} onChange={e=>updAssign(i,"site_id",e.target.value)}>
                {sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <span style={{fontSize:12,color:"var(--muted)"}}>FTE fraction</span>
              <input type="number" step="0.05" min={0} max={1} value={a.fte_fraction} onChange={e=>updAssign(i,"fte_fraction",e.target.value)}/>
              {a.id && (
                <input
                  type="text"
                  placeholder="Reason for change (optional)"
                  value={a.change_reason||""}
                  onChange={e=>updAssign(i,"change_reason",e.target.value)}
                  style={{width:220,fontFamily:"inherit",textAlign:"left"}}
                />
              )}
              <button className="btn sm danger" onClick={()=>rmAssign(i)}><IcoTrash/></button>
            </div>
          ))}
          <button className="btn sm" style={{marginTop:8}} onClick={addAssign}><IcoPlus/> Add site</button>

          {editingId && (
            <>
              <div className="divider"/>
              <div className="sub-section">History</div>
              <FTEHistoryTimeline physicianId={editingId}/>
            </>
          )}

          <div className="form-row" style={{marginTop:16}}>
            <button className="btn primary" onClick={save} disabled={saving}>{editingId ? "Save changes" : "Save provider"}</button>
            <button className="btn" onClick={cancelForm}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-title">Provider roster</div>
        <div style={{fontSize:12,color:"var(--muted)",marginBottom:12}}>
          {loadingRows ? "Loading…" : `Showing ${rows.length} of ${totalCount}`}
        </div>
        {loadingRows ? <Spinner/> : rows.length===0 ? <div className="empty">No providers match this filter.</div> : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr>
                <th>Life No</th><th>Name</th><th>Type</th><th>FTE</th>
                <th className="r">1.0 FTE hrs</th><th className="r">Clin hrs</th><th className="r">Role hrs</th>
                <th>Roles</th><th>Core</th><th>Sites</th><th>Notes</th><th></th>
              </tr></thead>
              <tbody>
                {rows.map(p => {
                  const coreSite = sites.find(s => s.id === p.core_site_id);
                  return (
                    <tr key={p.id}>
                      <td className="mono muted">{p.life_no||"—"}</td>
                      <td className="bold">
                        {p.last_name}, {p.first_name}
                        {!p.is_active && <span className="lbadge" style={{marginLeft:6,background:"var(--surface2)",color:"var(--muted)"}}>Inactive</span>}
                        {p.needs_fte_config && <span className="lbadge" style={{marginLeft:6,background:"var(--red-bg)",color:"var(--red)"}}>Needs FTE</span>}
                      </td>
                      <td><TypeBadge type={p.provider_type?.name||""}/></td>
                      <td className="mono">{parseFloat(p.total_fte||0).toFixed(2)}</td>
                      <td className="r mono">{p.yearly_hours}</td>
                      <td className="r mono" style={{color:"var(--green)"}}>{clinHrs(p)}</td>
                      <td className="r mono" style={{color:"var(--muted)"}}>{roleHrs(p)}</td>
                      <td>{p.roles.filter(r=>!r.end_date).map((r,i)=><span key={i} className="rtag">{r.role_type?.name||r.custom_title||"Role"} ({r.hours_credit}h)</span>)}</td>
                      <td>{coreSite?<span className="stag">{coreSite.name}</span>:"—"}</td>
                      <td>{p.assignments.filter(a=>!a.end_date).map((a,i)=>{const s=sites.find(x=>x.id===a.site_id);return <span key={i} className="stag">{s?.name||"?"} {a.fte_fraction}</span>;})}</td>
                      <td className="muted" style={{maxWidth:200,fontSize:11}}>{p.notes}</td>
                      <td style={{textAlign:"right",whiteSpace:"nowrap"}}>
                        <button className="btn sm" style={{marginRight:6}} onClick={()=>startEdit(p)}><IcoEdit/></button>
                        <button className="btn sm danger" onClick={()=>deletePhysician(p.id)}><IcoTrash/></button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

const HISTORY_DOT_COLOR = {assignment:"var(--accent)", role:"var(--green)", leave:"var(--red)"};

function FTEHistoryTimeline({physicianId}) {
  const [entries, setEntries] = useState([]);
  const [loading,  setLoading]  = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await apiFetch(`/physicians/${physicianId}/fte-history`);
        if (!cancelled) setEntries(data.entries);
      } catch {
        if (!cancelled) setEntries([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [physicianId]);

  if (loading) return <Spinner/>;
  if (entries.length === 0) return <div className="empty">No history yet.</div>;

  return (
    <div className="timeline">
      {entries.map((e,i) => (
        <div key={i} className="timeline-item">
          <div className="timeline-marker">
            <div className="timeline-dot" style={{background: HISTORY_DOT_COLOR[e.type] || "var(--faint)"}}/>
            {i < entries.length-1 && <div className="timeline-line"/>}
          </div>
          <div className="timeline-body">
            <div className="timeline-date">{e.date}</div>
            <div className="timeline-desc">{e.description}</div>
            {e.change_reason && <div className="timeline-reason">"{e.change_reason}"</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Sites ──────────────────────────────────────────────────────────────────
function SitesTab({onRefresh, onError}) {
  const [sites,     setSites]     = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [name,      setName]      = useState("");
  const [saving,    setSaving]    = useState(false);
  const [adding,    setAdding]    = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm,  setEditForm]  = useState({name:"", short_name:"", active:true});
  const [areaInputs,setAreaInputs]= useState({}); // siteId -> draft text for "add area"

  // Self-fetches the FULL roster (active + inactive) — the sites prop other
  // tabs get from App state stays active-only, since deactivated sites
  // shouldn't show up as assignable in physician/demand pickers. Reloading
  // here is what lets a deactivated site be found again to reactivate it.
  const loadSites = async () => {
    setLoading(true);
    try {
      const data = await apiFetch("/sites/?include_inactive=true");
      setSites(data);
    } catch (err) {
      onError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadSites(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Refreshes both this tab's own full list and the app-wide active-only one
  // (so a rename shows up immediately in other tabs' site pickers too).
  const refreshAll = async () => {
    await Promise.all([loadSites(), onRefresh()]);
  };

  const add = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await apiFetch("/sites/", {method: "POST", body: JSON.stringify({name: name.trim(), areas: []})});
      setName("");
      setAdding(false);
      await refreshAll();
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (s) => {
    setEditingId(s.id);
    setEditForm({name: s.name, short_name: s.short_name||"", active: s.active});
  };

  const cancelEdit = () => setEditingId(null);

  const saveEdit = async () => {
    if (!editForm.name.trim()) return;
    setSaving(true);
    try {
      await apiFetch(`/sites/${editingId}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: editForm.name.trim(),
          short_name: editForm.short_name.trim() || null,
          active: editForm.active,
        }),
      });
      setEditingId(null);
      await refreshAll();
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (s) => {
    try {
      await apiFetch(`/sites/${s.id}`, {method: "PATCH", body: JSON.stringify({active: !s.active})});
      await refreshAll();
    } catch (err) {
      onError(err.message);
    }
  };

  const addArea = async (siteId) => {
    const text = (areaInputs[siteId]||"").trim();
    if (!text) return;
    try {
      await apiFetch(`/sites/${siteId}/areas`, {method: "POST", body: JSON.stringify({name: text})});
      setAreaInputs(a => ({...a, [siteId]: ""}));
      await refreshAll();
    } catch (err) {
      onError(err.message);
    }
  };

  const removeArea = async (siteId, areaId) => {
    try {
      await apiFetch(`/sites/${siteId}/areas/${areaId}`, {method: "DELETE"});
      await refreshAll();
    } catch (err) {
      onError(err.message);
    }
  };

  return (
    <div>
      {!adding && (
        <div style={{marginBottom:16}}>
          <button className="btn primary" onClick={()=>{setAdding(true); setEditingId(null);}}><IcoPlus/> Add site</button>
        </div>
      )}

      {adding && (
        <div className="card">
          <div className="card-title">Add site</div>
          <div className="form-row">
            <div className="field"><label>Site name</label><input type="text" value={name} placeholder="e.g. MSH" onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==="Enter"&&add()} autoFocus/></div>
            <button className="btn primary" onClick={add} disabled={saving}>Add</button>
            <button className="btn" onClick={()=>{setAdding(false); setName("");}} disabled={saving}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-title">Clinical sites — {sites.length}</div>
        {loading ? <Spinner/> : sites.length===0 ? <div className="empty">No sites added.</div> : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th>Site name</th><th>Short name</th><th>Status</th><th>Areas</th><th></th></tr></thead>
              <tbody>
                {sites.map(s => (
                  <Fragment key={s.id}>
                    <tr>
                      <td className="bold">{s.name}</td>
                      <td className="muted">{s.short_name||"—"}</td>
                      <td style={{color: s.active?"var(--green)":"var(--muted)", fontWeight:600, fontSize:12}}>
                        {s.active ? "Active" : "Inactive"}
                      </td>
                      <td>
                        {(s.areas||[]).length===0 ? <span className="muted" style={{fontSize:12}}>—</span> :
                          s.areas.map(a=><span key={a.id} className="rtag">{a.name}</span>)}
                      </td>
                      <td style={{textAlign:"right",whiteSpace:"nowrap"}}>
                        <button className="btn sm" style={{marginRight:6}} onClick={()=>{ setAdding(false); s.id===editingId ? cancelEdit() : startEdit(s); }}><IcoEdit/></button>
                        <button className="btn sm" onClick={()=>toggleActive(s)}>{s.active ? "Deactivate" : "Reactivate"}</button>
                      </td>
                    </tr>
                    {editingId===s.id && (
                      <tr>
                        <td colSpan={5} style={{background:"var(--surface2)",padding:"16px 18px"}}>
                          <div className="form-row" style={{marginBottom:14}}>
                            <div className="field"><label>Name</label><input type="text" value={editForm.name} onChange={e=>setEditForm(f=>({...f,name:e.target.value}))}/></div>
                            <div className="field"><label>Short name</label><input type="text" style={{width:100}} value={editForm.short_name} onChange={e=>setEditForm(f=>({...f,short_name:e.target.value}))} placeholder="e.g. MSH"/></div>
                            <div className="field"><label>Status</label>
                              <select value={editForm.active?"true":"false"} onChange={e=>setEditForm(f=>({...f,active:e.target.value==="true"}))} style={{minWidth:110}}>
                                <option value="true">Active</option>
                                <option value="false">Inactive</option>
                              </select>
                            </div>
                            <button className="btn primary" onClick={saveEdit} disabled={saving}>Save changes</button>
                            <button className="btn" onClick={cancelEdit} disabled={saving}>Cancel</button>
                          </div>

                          <div className="sub-section" style={{marginTop:4}}>Areas</div>
                          <div style={{marginBottom:10}}>
                            {(s.areas||[]).length===0 && <span style={{fontSize:12,color:"var(--faint)"}}>No areas yet.</span>}
                            {(s.areas||[]).map(a=>(
                              <span key={a.id} className="rtag" style={{display:"inline-flex",alignItems:"center",gap:5}}>
                                {a.name}
                                <button
                                  onClick={()=>removeArea(s.id,a.id)}
                                  aria-label={`Remove ${a.name}`}
                                  style={{background:"none",border:"none",cursor:"pointer",color:"inherit",fontWeight:700,lineHeight:1,padding:0,fontSize:13}}
                                >×</button>
                              </span>
                            ))}
                          </div>
                          <div className="form-row">
                            <div className="field"><label>Add area</label>
                              <input
                                type="text"
                                placeholder="e.g. Peds ED"
                                style={{width:160}}
                                value={areaInputs[s.id]||""}
                                onChange={e=>setAreaInputs(a=>({...a,[s.id]:e.target.value}))}
                                onKeyDown={e=>e.key==="Enter"&&addArea(s.id)}
                              />
                            </div>
                            <button className="btn sm" onClick={()=>addArea(s.id)}><IcoPlus/> Add area</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Monthly demand ─────────────────────────────────────────────────────────
function DemandTab({sites, demand, onDemandUpdate}) {
  const [draft, setDraft] = useState(demand);
  const [status, setStatus] = useState({}); // `${siteId}|${key}` -> "saving" | "saved" | "error"
  const timers = useRef({});

  useEffect(() => { setDraft(demand); }, [demand]);
  useEffect(() => () => { Object.values(timers.current).forEach(clearTimeout); }, []);

  const commit = async (siteId, key, val) => {
    const cellKey = `${siteId}|${key}`;
    clearTimeout(timers.current[cellKey]);
    const [yearStr, monthStr] = key.split("-");
    setStatus(s => ({...s, [cellKey]: "saving"}));
    try {
      await onDemandUpdate(siteId, parseInt(yearStr), parseInt(monthStr), parseInt(val)||0);
      setStatus(s => ({...s, [cellKey]: "saved"}));
      setTimeout(() => setStatus(s => { const {[cellKey]:_, ...rest} = s; return rest; }), 1200);
    } catch {
      setStatus(s => ({...s, [cellKey]: "error"}));
    }
  };

  // Auto-saves ~700ms after the last keystroke, and immediately on blur —
  // relying on blur alone misses changes from spinner clicks/scroll-wheel
  // that don't move focus away from the field.
  const handleChange = (siteId, key, val) => {
    setDraft(d => ({...d, [siteId]: {...(d[siteId]||{}), [key]: parseInt(val)||0}}));
    const cellKey = `${siteId}|${key}`;
    clearTimeout(timers.current[cellKey]);
    timers.current[cellKey] = setTimeout(() => commit(siteId, key, val), 700);
  };

  const handleBlur = (siteId, key, val) => commit(siteId, key, val);

  return (
    <div>
      {sites.length===0 && <div className="card"><div className="empty">Add sites first.</div></div>}
      {sites.map(site=>(
        <div key={site.id} className="card">
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline",marginBottom:16}}>
            <div className="card-title" style={{margin:0}}>{site.name}</div>
            <span style={{fontSize:11,color:"var(--muted)"}}>Clinical hours required per month</span>
          </div>
          <div className="demand-grid">
            {MONTHS_LIST.map(({key,label})=>{
              const cellKey = `${site.id}|${key}`;
              const cellStatus = status[cellKey];
              return (
                <div key={key} className="demand-cell">
                  <label>
                    {label}
                    {cellStatus==="saving" && <span className="demand-status saving">Saving…</span>}
                    {cellStatus==="saved"  && <span className="demand-status saved">Saved</span>}
                    {cellStatus==="error"  && <span className="demand-status error">Error</span>}
                  </label>
                  <input
                    type="number" min={0}
                    className={cellStatus==="error" ? "input-error" : undefined}
                    value={(draft[site.id]||{})[key]||0}
                    onChange={e=>handleChange(site.id, key, e.target.value)}
                    onBlur={e=>handleBlur(site.id, key, e.target.value)}
                  />
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Time allocations (Phase D) ────────────────────────────────────────────────
const TALLOC_YEARS = [YEAR-1, YEAR, YEAR+1];

function TimeAllocationsTab({physicians, onRefresh, onError}) {
  const [physicianId,  setPhysicianId]  = useState("");
  const [year,          setYear]         = useState(YEAR);
  const [categories,    setCategories]   = useState([]);
  const [yearlyHours,   setYearlyHours]  = useState(0);
  const [original,      setOriginal]     = useState({}); // {catId: {month: {hours, change_reason}}}
  const [draft,         setDraft]        = useState({}); // {catId: {month: "12"}}
  const [changeReason,  setChangeReason] = useState("");
  const [loadingGrid,   setLoadingGrid]  = useState(false);
  const [saving,        setSaving]       = useState(false);
  const [needsConfig,   setNeedsConfig]  = useState([]);
  const [loadingNeeds,  setLoadingNeeds] = useState(true);

  useEffect(() => {
    apiFetch("/time-categories").then(setCategories).catch(err=>onError(err.message));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadNeedsConfig = async () => {
    setLoadingNeeds(true);
    try {
      const rows = await apiFetch(`/time-allocations/check?year=${year}`);
      setNeedsConfig(rows);
    } catch (err) {
      onError(err.message);
    } finally {
      setLoadingNeeds(false);
    }
  };
  useEffect(() => { loadNeedsConfig(); }, [year]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadGrid = async () => {
    if (!physicianId) { setOriginal({}); setDraft({}); return; }
    setLoadingGrid(true);
    try {
      const data = await apiFetch(`/physicians/${physicianId}/time-allocations?year=${year}`);
      setYearlyHours(data.yearly_hours);
      const orig = {}, drf = {};
      data.categories.forEach(cat => {
        orig[cat.time_category_id] = {};
        drf[cat.time_category_id] = {};
        cat.cells.forEach(cell => {
          orig[cat.time_category_id][cell.month] = {hours: parseFloat(cell.hours)||0, change_reason: cell.change_reason||null};
          drf[cat.time_category_id][cell.month] = String(cell.hours);
        });
      });
      setOriginal(orig);
      setDraft(drf);
    } catch (err) {
      onError(err.message);
    } finally {
      setLoadingGrid(false);
    }
  };
  useEffect(() => { loadGrid(); }, [physicianId, year]); // eslint-disable-line react-hooks/exhaustive-deps

  const setCell = (catId, month, value) => {
    setDraft(d => ({...d, [catId]: {...(d[catId]||{}), [month]: value}}));
  };

  const cellChanged = (catId, month) => {
    const orig = original[catId]?.[month];
    const val = parseFloat((draft[catId]||{})[month]) || 0;
    return orig !== undefined && val !== orig.hours;
  };

  const totals = useMemo(() => {
    let clinical = 0, nonClinical = 0;
    categories.forEach(cat => {
      const monthVals = draft[cat.id] || {};
      const catTotal = MONTHS_LIST.reduce((s,m) => s + (parseFloat(monthVals[m.month]) || 0), 0);
      if (cat.is_clinical) clinical += catTotal; else nonClinical += catTotal;
    });
    return {clinical, nonClinical, total: clinical + nonClinical};
  }, [draft, categories]);

  const variance = yearlyHours - totals.total; // positive = under-allocated, negative = over-allocated
  const checkOk = Boolean(physicianId) && variance === 0;

  const save = async () => {
    if (!physicianId) return;
    setSaving(true);
    try {
      const allocations = [];
      categories.forEach(cat => {
        const monthVals = draft[cat.id] || {};
        MONTHS_LIST.forEach(m => {
          const hours = parseFloat(monthVals[m.month]) || 0;
          const orig = original[cat.id]?.[m.month];
          const changed = !orig || hours !== orig.hours;
          allocations.push({
            time_category_id: cat.id,
            month: m.month,
            hours,
            change_reason: changed ? (changeReason.trim() || null) : (orig?.change_reason ?? null),
          });
        });
      });
      await apiFetch(`/physicians/${physicianId}/time-allocations`, {
        method: "PUT",
        body: JSON.stringify({year, allocations}),
      });
      setChangeReason("");
      await loadGrid();
      await loadNeedsConfig();
      await onRefresh(); // syncs clinical_pct / needs_time_allocation_config into the app-wide roster
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const clinicalCats = categories.filter(c=>c.is_clinical);
  const nonClinicalCats = categories.filter(c=>!c.is_clinical);
  const selectedPhysician = physicians.find(p=>p.id===physicianId);
  const ready = physicianId && !loadingGrid && categories.length>0;

  const renderCategoryRow = (cat) => (
    <tr key={cat.id}>
      <td className="bold" style={{whiteSpace:"nowrap"}}>{cat.name}</td>
      {MONTHS_LIST.map(m => (
        <td key={m.key} style={{padding:"4px 3px"}}>
          <input
            type="number" min={0} step="0.5"
            className={`talloc-input ${cellChanged(cat.id, m.month)?"changed":""}`}
            value={(draft[cat.id]||{})[m.month] ?? "0"}
            onChange={e=>setCell(cat.id, m.month, e.target.value)}
          />
        </td>
      ))}
      <td className="r mono bold">
        {MONTHS_LIST.reduce((s,m) => s + (parseFloat((draft[cat.id]||{})[m.month]) || 0), 0)}
      </td>
    </tr>
  );

  return (
    <div>
      <div className="card">
        <div className="card-title">Needs configuration{!loadingNeeds && ` — ${needsConfig.length}`}</div>
        {loadingNeeds ? <Spinner/> : needsConfig.length===0 ? (
          <div className="empty">Every active provider's {year} hours are fully accounted for.</div>
        ) : (
          <div>
            {needsConfig.map(r=>(
              <div key={r.physician_id} className="talloc-needs-row">
                <div>
                  <span className="bold">{r.last_name}, {r.first_name}</span>
                  <span className="muted" style={{marginLeft:8,fontSize:12}}>
                    {r.allocated_hours}h of {r.yearly_hours}h — {Math.abs(r.hours_variance)}h {r.hours_variance>0?"short":"over"}
                  </span>
                </div>
                <button className="btn sm" onClick={()=>setPhysicianId(r.physician_id)}>Configure</button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="form-row" style={{marginBottom:0}}>
          <div className="field" style={{flex:1}}><label>Provider</label>
            <PhysicianSearchSelect
              physicians={physicians}
              value={physicianId}
              onChange={setPhysicianId}
              placeholder="Search providers…"
              style={{minWidth:240}}
            />
          </div>
          <div className="field"><label>Year</label>
            <select value={year} onChange={e=>setYear(parseInt(e.target.value))} style={{minWidth:100}}>
              {TALLOC_YEARS.map(y=><option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>
      </div>

      {!physicianId ? (
        <div className="card"><div className="empty">Select a provider above to view or edit their time allocations.</div></div>
      ) : !ready ? (
        <div className="card"><Spinner/></div>
      ) : (
        <>
          <div className="card">
            <div className="card-title">{selectedPhysician ? `${selectedPhysician.last_name}, ${selectedPhysician.first_name}` : ""} — {year}</div>
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Category</th>
                    {MONTHS_LIST.map(m=><th key={m.key} className="r" style={{minWidth:52}}>{m.label}</th>)}
                    <th className="r">Total</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="talloc-section-row"><td colSpan={14}>Clinical</td></tr>
                  {clinicalCats.map(renderCategoryRow)}
                  <tr className="talloc-section-row"><td colSpan={14}>Non-clinical</td></tr>
                  {nonClinicalCats.map(renderCategoryRow)}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <div className="kpi-grid" style={{gridTemplateColumns:"repeat(3,1fr)"}}>
              <div className="kpi">
                <div className="kpi-label">Clinical total</div>
                <div className="kpi-value">{totals.clinical.toLocaleString()}</div>
                <div className="kpi-sub">hours / yr</div>
              </div>
              <div className="kpi">
                <div className="kpi-label">Non-clinical total</div>
                <div className="kpi-value">{totals.nonClinical.toLocaleString()}</div>
                <div className="kpi-sub">hours / yr</div>
              </div>
              <div className={`kpi ${checkOk?"green":"red"}`}>
                <div className="kpi-label">Total hrs check</div>
                <div className="kpi-value">{totals.total.toLocaleString()}</div>
                <div className="kpi-sub">
                  {checkOk
                    ? `✓ matches ${yearlyHours}h yearly hours`
                    : `${Math.abs(variance)}h ${variance>0?"under":"over"}-allocated (target ${yearlyHours}h)`}
                </div>
              </div>
            </div>
            <div className="form-row" style={{marginTop:4}}>
              <div className="field" style={{flex:1}}>
                <label>Reason for change (optional — applied to any cells you edited)</label>
                <input type="text" style={{minWidth:"100%"}} value={changeReason} onChange={e=>setChangeReason(e.target.value)} placeholder="e.g. K Award start, added nocturnist shifts"/>
              </div>
              <button className="btn primary" onClick={save} disabled={saving}>{saving?"Saving…":"Save"}</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Leaves ─────────────────────────────────────────────────────────────────
const BLANK_LEAVE_FORM = {physician_id:"",leave_type:LEAVE_TYPES[0],start_date:"",end_date:"",notes:"",is_partial:false,fte_during_leave:""};

function LeavesTab({leaves, physicians, onRefresh, onError}) {
  const [form,      setForm]      = useState(BLANK_LEAVE_FORM);
  const [editingId, setEditingId] = useState(null);
  const [saving,    setSaving]    = useState(false);

  const startEdit = (l) => {
    setEditingId(l.id);
    setForm({
      physician_id: l.physician_id, leave_type: l.leave_type, start_date: l.start_date, end_date: l.end_date, notes: l.notes||"",
      is_partial: !!l.is_partial,
      fte_during_leave: l.fte_during_leave != null ? String(Math.round(parseFloat(l.fte_during_leave)*100)) : "",
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(BLANK_LEAVE_FORM);
  };

  const save = async () => {
    if (!form.physician_id || !form.start_date || !form.end_date) return;
    if (form.is_partial && (form.fte_during_leave === "" || isNaN(parseFloat(form.fte_during_leave)))) {
      onError("Enter what percentage of normal time they're still covering during this leave.");
      return;
    }
    setSaving(true);
    try {
      const body = {
        physician_id: form.physician_id,
        leave_type: form.leave_type,
        start_date: form.start_date,
        end_date: form.end_date,
        notes: form.notes,
        is_partial: form.is_partial,
        // "No" -> null (today's default: a full wipe-out for the overlapping period).
        // "Yes" -> the fraction of normal time still covered, 0-100% in the UI,
        // stored as fte_during_leave 0-1 — see _leave_reduction in capacity.py.
        fte_during_leave: form.is_partial
          ? Math.min(1, Math.max(0, parseFloat(form.fte_during_leave) / 100))
          : null,
      };
      if (editingId) {
        await apiFetch(`/leaves/${editingId}`, {method: "PUT", body: JSON.stringify(body)});
        setEditingId(null);
      } else {
        await apiFetch("/leaves/", {method: "POST", body: JSON.stringify(body)});
      }
      setForm(BLANK_LEAVE_FORM);
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const deleteLeave = async (id) => {
    try {
      await apiFetch(`/leaves/${id}`, {method: "DELETE"});
      await onRefresh();
    } catch (err) {
      onError(err.message);
    }
  };

  return (
    <div>
      <div className="info-box">
        Leave events reduce a provider's available hours proportionally for the months they overlap. A full-month leave removes all availability for that provider at all their sites for that month.
      </div>
      <div className="card">
        <div className="card-title">{editingId ? "Edit leave event" : "Add leave event"}</div>
        <div className="form-row" style={{marginBottom:10}}>
          <div className="field"><label>Provider</label>
            <PhysicianSearchSelect
              physicians={physicians}
              value={form.physician_id}
              onChange={id=>setForm(f=>({...f,physician_id:id}))}
              placeholder="Search providers…"
              style={{minWidth:220}}
            />
          </div>
          <div className="field"><label>Leave type</label>
            <select value={form.leave_type} onChange={e=>setForm(f=>({...f,leave_type:e.target.value}))} style={{minWidth:200}}>
              {LEAVE_TYPES.map(t=><option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="field"><label>Start date</label><input type="date" value={form.start_date} onChange={e=>setForm(f=>({...f,start_date:e.target.value}))}/></div>
          <div className="field"><label>End date</label><input type="date" value={form.end_date} onChange={e=>setForm(f=>({...f,end_date:e.target.value}))}/></div>
          <button className="btn primary" onClick={save} disabled={saving}>
            {editingId ? <>Save changes</> : <><IcoPlus/> Add</>}
          </button>
          {editingId && <button className="btn" onClick={cancelEdit} disabled={saving}>Cancel</button>}
        </div>
        <div className="field" style={{marginBottom:14}}>
          <label>Will this physician make up these hours?</label>
          <div style={{display:"flex",flexDirection:"column",gap:6,marginTop:4}}>
            <label style={{display:"flex",alignItems:"center",gap:8,fontSize:13,fontWeight:400,textTransform:"none",letterSpacing:"normal",color:"var(--text)",cursor:"pointer"}}>
              <input type="radio" name="leave-makeup" checked={!form.is_partial} onChange={()=>setForm(f=>({...f,is_partial:false,fte_during_leave:""}))}/>
              No — hours are simply reduced for this period
            </label>
            <label style={{display:"flex",alignItems:"center",gap:8,fontSize:13,fontWeight:400,textTransform:"none",letterSpacing:"normal",color:"var(--text)",cursor:"pointer"}}>
              <input type="radio" name="leave-makeup" checked={form.is_partial} onChange={()=>setForm(f=>({...f,is_partial:true}))}/>
              Yes — they'll cover it, reduce by a different amount
            </label>
            {form.is_partial && (
              <div style={{display:"flex",alignItems:"center",gap:8,marginLeft:24,marginTop:2}}>
                <span style={{fontSize:12,color:"var(--muted)"}}>Still covering</span>
                <input
                  type="number" min={0} max={100} step="5" style={{width:80}}
                  value={form.fte_during_leave}
                  onChange={e=>setForm(f=>({...f,fte_during_leave:e.target.value}))}
                  placeholder="e.g. 50"
                />
                <span style={{fontSize:12,color:"var(--muted)"}}>% of their normal time during this leave</span>
              </div>
            )}
          </div>
        </div>
        <div className="form-row">
          <div className="field" style={{flex:1}}>
            <label>Notes</label>
            <input type="text" style={{minWidth:"100%"}} value={form.notes} onChange={e=>setForm(f=>({...f,notes:e.target.value}))} placeholder="e.g. K Award protected time, grant funded through 7/31/27"/>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-title">Leave events — {leaves.length}</div>
        {leaves.length===0 ? <div className="empty">No leave events recorded.</div> : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th>Provider</th><th>Type</th><th>Leave</th><th>Coverage</th><th>Start</th><th>End</th><th className="r">Days</th><th>Notes</th><th></th></tr></thead>
              <tbody>
                {leaves.map(l=>{
                  const ph = physicians.find(p => p.id === l.physician_id);
                  const days = l.start_date && l.end_date
                    ? Math.round((new Date(l.end_date+"T00:00:00")-new Date(l.start_date+"T00:00:00"))/86400000)+1
                    : "—";
                  return (
                    <tr key={l.id}>
                      <td className="bold">{ph?`${ph.last_name}, ${ph.first_name}`:"Unknown"}</td>
                      <td>{ph&&<TypeBadge type={ph.provider_type?.name||""}/>}</td>
                      <td><LeaveBadge type={l.leave_type}/></td>
                      <td>
                        {l.fte_during_leave != null
                          ? <span className="lbadge" style={{background:"var(--accent-bg)",color:"var(--accent)"}}>{Math.round(parseFloat(l.fte_during_leave)*100)}% covered</span>
                          : <span className="lbadge" style={{background:"var(--red-bg)",color:"var(--red)"}}>Full wipe-out</span>}
                      </td>
                      <td className="mono">{l.start_date}</td>
                      <td className="mono">{l.end_date}</td>
                      <td className="r mono">{days}d</td>
                      <td className="muted">{l.notes}</td>
                      <td style={{textAlign:"right",whiteSpace:"nowrap"}}>
                        <button className="btn sm" style={{marginRight:6}} onClick={()=>startEdit(l)}><IcoEdit/></button>
                        <button className="btn sm danger" onClick={()=>deleteLeave(l.id)}><IcoTrash/></button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Staffing plan ──────────────────────────────────────────────────────────
function physSiteAnnual(ph, siteId, leaves, year) {
  const asgn = ph.assignments.find(a => a.site_id === siteId);
  if (!asgn) return null;
  const fte = parseFloat(asgn.fte_fraction);
  const phLeaves = leaves.filter(l => l.physician_id === ph.id);
  let totalH = 0, totalFTE = 0;
  for (let m = 1; m <= 12; m++) {
    const dim = new Date(year, m, 0).getDate();
    const mS = new Date(year, m-1, 1), mE = new Date(year, m-1, dim);
    let red = 0;
    for (const lv of phLeaves) {
      const ls = new Date(lv.start_date+"T00:00:00"), le = new Date(lv.end_date+"T00:00:00");
      if (ls > mE || le < mS) continue;
      const os = ls < mS ? mS : ls, oe = le > mE ? mE : le;
      const of_ = (Math.round((oe-os)/86400000)+1) / dim;
      const r = lv.fte_during_leave != null ? of_*(1-parseFloat(lv.fte_during_leave)) : of_;
      red = Math.min(1, red + r);
    }
    const avail = 1 - red;
    totalH   += (ph.yearly_hours/12) * fte * avail;
    totalFTE += fte * avail;
  }
  const cp = parseFloat(ph.clinical_pct || 0);
  return {
    fte,
    availH:  Math.round(totalH),
    clinH:   Math.round(totalH * cp),
    nclinH:  Math.round(totalH * (1-cp)),
    avgFTE:  Math.round(totalFTE/12*100)/100,
  };
}

const gSum = (items) => items.reduce((a,d) => ({
  fte:    Math.round((a.fte    + d.fte)    * 100) / 100,
  availH: a.availH + d.availH,
  clinH:  a.clinH  + d.clinH,
  nclinH: a.nclinH + d.nclinH,
  avgFTE: Math.round((a.avgFTE + d.avgFTE) * 100) / 100,
}), {fte:0, availH:0, clinH:0, nclinH:0, avgFTE:0});

function StaffingTab({sites, physicians, leaves, capacity}) {
  return (
    <div>
      {sites.length===0 && <div className="card"><div className="empty">No sites configured.</div></div>}
      {sites.map(site => {
        const sitePhs = physicians.filter(p => p.is_active && p.assignments.some(a => a.site_id===site.id));

        const build = (fn) => sitePhs
          .filter(fn)
          .map(ph => ({ph, data: physSiteAnnual(ph, site.id, leaves, YEAR)}))
          .filter(x => x.data);

        const phRows  = build(p => ["MD","DO"].includes(p.provider_type?.name||""));
        const appRows = build(p => ["PA","NP"].includes(p.provider_type?.name||""));
        const felRows = build(p => (p.provider_type?.name||"").startsWith("Fellow"));

        const phSub  = gSum(phRows.map(x=>x.data));
        const appSub = gSum(appRows.map(x=>x.data));
        const felSub = gSum(felRows.map(x=>x.data));
        const total  = gSum([phSub, appSub, felSub]);

        const capRows   = (capacity?.rows||[]).filter(r => r.site_id===site.id);
        const annualReqH = Math.round(capRows.reduce((s,r)=>s+r.required_hours,0));
        const avgReqFTE  = capRows.length
          ? Math.round(capRows.reduce((s,r)=>s+r.required_fte,0)/capRows.length*100)/100
          : 0;
        const hGap   = total.availH - annualReqH;
        const fteGap = Math.round((total.avgFTE - avgReqFTE)*100)/100;

        const GHdr = ({label}) => (
          <tr>
            <td colSpan={6} style={{background:"var(--surface2)",color:"var(--muted)",fontWeight:600,fontSize:10,textTransform:"uppercase",letterSpacing:".08em",padding:"7px 12px"}}>
              {label}
            </td>
          </tr>
        );
        const PRow = ({ph, data}) => (
          <tr>
            <td className="bold">{ph.last_name}, {ph.first_name}</td>
            <td><TypeBadge type={ph.provider_type?.name||""}/></td>
            <td className="r mono">{data.fte.toFixed(2)}</td>
            <td className="r mono">{data.availH.toLocaleString()}</td>
            <td className="r mono" style={{color:"var(--green)"}}>{data.clinH.toLocaleString()}</td>
            <td className="r mono" style={{color:"var(--muted)"}}>{data.nclinH.toLocaleString()}</td>
          </tr>
        );
        const SRow = ({label, data}) => (
          <tr style={{background:"var(--surface2)"}}>
            <td colSpan={2} style={{fontWeight:600,fontSize:12,color:"var(--muted)",paddingLeft:20}}>↳ {label}</td>
            <td className="r mono bold">{data.fte.toFixed(2)}</td>
            <td className="r mono bold">{data.availH.toLocaleString()}</td>
            <td className="r mono bold" style={{color:"var(--green)"}}>{data.clinH.toLocaleString()}</td>
            <td className="r mono bold" style={{color:"var(--muted)"}}>{data.nclinH.toLocaleString()}</td>
          </tr>
        );

        return (
          <div key={site.id} className="card">
            <div className="card-title">{site.name}</div>
            {sitePhs.length===0 ? <div className="empty">No providers assigned.</div> : (
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Provider</th><th>Type</th>
                      <th className="r">Site FTE</th>
                      <th className="r">Avail hrs / yr</th>
                      <th className="r">Clin hrs / yr</th>
                      <th className="r">Non-clin / yr</th>
                    </tr>
                  </thead>
                  <tbody>
                    {phRows.length>0 && <>
                      <GHdr label="Physicians (MD / DO)"/>
                      {phRows.map(x=><PRow key={x.ph.id} ph={x.ph} data={x.data}/>)}
                      <SRow label="Physicians total" data={phSub}/>
                    </>}
                    {appRows.length>0 && <>
                      <GHdr label="APPs (PA / NP)"/>
                      {appRows.map(x=><PRow key={x.ph.id} ph={x.ph} data={x.data}/>)}
                      <SRow label="APPs total" data={appSub}/>
                    </>}
                    {felRows.length>0 && <>
                      <GHdr label="Fellows"/>
                      {felRows.map(x=><PRow key={x.ph.id} ph={x.ph} data={x.data}/>)}
                      <SRow label="Fellows total" data={felSub}/>
                    </>}

                    <tr style={{borderTop:"2px solid var(--border2)"}}>
                      <td colSpan={2} style={{fontWeight:700,fontSize:13}}>Scheduled total</td>
                      <td className="r mono bold">{total.fte.toFixed(2)}</td>
                      <td className="r mono bold">{total.availH.toLocaleString()}</td>
                      <td className="r mono bold" style={{color:"var(--green)"}}>{total.clinH.toLocaleString()}</td>
                      <td className="r mono bold" style={{color:"var(--muted)"}}>{total.nclinH.toLocaleString()}</td>
                    </tr>
                    <tr>
                      <td colSpan={2} style={{color:"var(--muted)",fontWeight:600}}>Required (annual demand)</td>
                      <td className="r" style={{color:"var(--muted)",fontFamily:"'DM Mono',monospace",fontSize:12}}>{avgReqFTE.toFixed(2)} avg FTE</td>
                      <td className="r mono" style={{color:"var(--muted)"}}>{annualReqH.toLocaleString()}</td>
                      <td colSpan={2}/>
                    </tr>
                    <tr style={{borderTop:"1px solid var(--border2)"}}>
                      <td colSpan={2} style={{fontWeight:700}}>Staffing margin</td>
                      <td className="r"><Gap val={fteGap}/></td>
                      <td className="r"><Gap val={hGap} unit=" hrs"/></td>
                      <td colSpan={2}/>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Audit log ──────────────────────────────────────────────────────────────
const AUDIT_OMIT_KEYS = new Set([
  "id","created_at","updated_at","assignments","roles","provider_type","areas","role_type","total_fte",
  "created_by","updated_by", // redundant with the User column
]);

function formatAuditValue(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "object") return JSON.stringify(v);
  const s = String(v);
  return s.length > 30 ? s.slice(0,27)+"…" : s;
}

// Scalar, non-housekeeping fields only — drops relationships/nested objects
// and columns (id, timestamps) that aren't useful in a change summary.
function auditFields(values) {
  if (!values) return {};
  return Object.fromEntries(
    Object.entries(values).filter(([k,v]) => !AUDIT_OMIT_KEYS.has(k) && typeof v !== "object")
  );
}

function summarizeAudit({action, old_values, new_values}) {
  if (action === "INSERT") {
    const parts = Object.entries(auditFields(new_values)).slice(0,4).map(([k,v])=>`${k}=${formatAuditValue(v)}`);
    return parts.length ? parts.join(", ") : "—";
  }
  if (action === "DELETE") {
    const parts = Object.entries(auditFields(old_values)).slice(0,4).map(([k,v])=>`${k}=${formatAuditValue(v)}`);
    return parts.length ? parts.join(", ") : "—";
  }
  if (action === "UPDATE") {
    const oldF = auditFields(old_values), newF = auditFields(new_values);
    const changedKeys = Object.keys(newF).filter(k => JSON.stringify(newF[k]) !== JSON.stringify(oldF[k]));
    if (!changedKeys.length) return "no field changes";
    const shown = changedKeys.slice(0,3).map(k => `${k}: ${formatAuditValue(oldF[k])} → ${formatAuditValue(newF[k])}`);
    return shown.join("; ") + (changedKeys.length > 3 ? ` (+${changedKeys.length-3} more)` : "");
  }
  return "—";
}

function AuditLogTab({onError}) {
  const [entries,      setEntries]      = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [tableFilter,  setTableFilter]  = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [startDate,    setStartDate]    = useState("");
  const [endDate,      setEndDate]      = useState("");

  const hasFilters = Boolean(tableFilter || actionFilter || startDate || endDate);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (tableFilter)  params.set("table_name", tableFilter);
        if (actionFilter) params.set("action", actionFilter);
        if (startDate)    params.set("start_date", startDate);
        if (endDate)      params.set("end_date", endDate);
        const data = await apiFetch(`/audit-log/?${params.toString()}`);
        if (!cancelled) setEntries(data);
      } catch (err) {
        if (!cancelled) { onError(err.message); setEntries([]); }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [tableFilter, actionFilter, startDate, endDate]); // eslint-disable-line react-hooks/exhaustive-deps

  const clearFilters = () => { setTableFilter(""); setActionFilter(""); setStartDate(""); setEndDate(""); };

  return (
    <div>
      <div className="card">
        <div className="card-title">Filters</div>
        <div className="form-row">
          <div className="field"><label>Table</label>
            <select value={tableFilter} onChange={e=>setTableFilter(e.target.value)} style={{minWidth:170}}>
              <option value="">All tables</option>
              {AUDIT_TABLES.map(t=><option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="field"><label>Action</label>
            <select value={actionFilter} onChange={e=>setActionFilter(e.target.value)} style={{minWidth:130}}>
              <option value="">All actions</option>
              {AUDIT_ACTIONS.map(a=><option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="field"><label>From</label><input type="date" value={startDate} onChange={e=>setStartDate(e.target.value)}/></div>
          <div className="field"><label>To</label><input type="date" value={endDate} onChange={e=>setEndDate(e.target.value)}/></div>
          {hasFilters && <button className="btn" onClick={clearFilters}>Clear filters</button>}
        </div>
      </div>
      <div className="card">
        <div className="card-title">Audit log{!loading && ` — ${entries.length}`}</div>
        {loading ? <Spinner/> : entries.length===0 ? (
          <div className="empty">{hasFilters ? "No audit log entries match these filters." : "No audit log entries yet."}</div>
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr><th>Timestamp</th><th>User</th><th>Action</th><th>Table</th><th>Summary</th></tr></thead>
              <tbody>
                {entries.map(e=>(
                  <tr key={e.id}>
                    <td className="mono muted" style={{whiteSpace:"nowrap"}}>{new Date(e.created_at).toLocaleString()}</td>
                    <td>{e.user_email || "—"}</td>
                    <td><ActionBadge action={e.action}/></td>
                    <td className="mono">{e.table_name}</td>
                    <td className="audit-summary">{summarizeAudit(e)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── App shell ──────────────────────────────────────────────────────────────
const NAV = [
  {id:"dashboard",label:"Dashboard",Icon:IcoDash},
  {id:"physicians",label:"Providers",Icon:IcoUsers},
  {id:"sites",label:"Sites",Icon:IcoSite},
  {id:"demand",label:"Monthly demand",Icon:IcoChart},
  {id:"leaves",   label:"Leaves",         Icon:IcoLeave},
  {id:"staffing", label:"Staffing",        Icon:IcoStaff},
  {id:"time-allocations", label:"Time Allocations", Icon:IcoGrid},
  {id:"audit",    label:"Audit Log",       Icon:IcoAudit, adminOnly:true},
];
const PAGE = {
  dashboard: {title:"Dashboard",sub:"Pre-scheduling capacity overview"},
  physicians:{title:"Providers",sub:"MD, DO, PA, NP, and Fellows"},
  sites:     {title:"Sites",sub:"Clinical sites"},
  demand:    {title:"Monthly demand",sub:"Required clinical hours per site per month"},
  leaves:    {title:"Leave events",   sub:"FMLA, LOA, research protected time, and other absences"},
  staffing:  {title:"Staffing Plan",  sub:"Annual provider hours by site — Physicians · APPs · Fellows"},
  "time-allocations": {title:"Time Allocations", sub:"Category hours by month — derives clinical %"},
  audit:     {title:"Audit Log",      sub:"Who changed what, and when"},
};

export default function App() {
  // ── Auth ───────────────────────────────────────────────────────────────
  const [token, setTokenState] = useState(null); // access token, in-memory only
  const [user,  setUser]       = useState(null);

  const setToken = (t) => { setApiAuthToken(t); setTokenState(t); };

  useEffect(() => {
    setOnAuthExpired(() => { setToken(null); setUser(null); });
  }, []);

  const handleLogin = async (email, password) => {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({email, password}),
    });
    setToken(data.access_token);
    try {
      const me = await apiFetch("/auth/me");
      setUser(me);
    } catch (err) {
      setToken(null);
      throw err;
    }
  };

  const handleLogout = async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {
      // already logged out server-side or unreachable — clear local state regardless
    }
    setToken(null);
    setUser(null);
  };

  const loggedIn = Boolean(token && user);

  const [tab,          setTab]          = useState("dashboard");
  const [sites,        setSites]        = useState([]);
  const [physicians,   setPhysicians]   = useState([]);
  const [leaves,       setLeaves]       = useState([]);
  const [demandRows,   setDemandRows]   = useState([]);
  const [capacity,     setCapacity]     = useState({rows:[]});
  const [lookupTables, setLookupTables] = useState({provider_types:[],role_types:[]});
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);

  const demandMap = useMemo(() => {
    const map = {};
    for (const row of demandRows) {
      if (!map[row.site_id]) map[row.site_id] = {};
      const key = `${row.year}-${String(row.month).padStart(2,"0")}`;
      map[row.site_id][key] = row.hours_required;
    }
    return map;
  }, [demandRows]);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, p, l, d, c, lt] = await Promise.all([
        apiFetch("/sites/"),
        apiFetch("/physicians/?is_active=true"),
        apiFetch(`/leaves/?year=${YEAR}`),
        apiFetch(`/demand/?year=${YEAR}`),
        apiFetch(`/capacity?year=${YEAR}`),
        apiFetch("/physicians/lookup-tables"),
      ]);
      setSites(s); setPhysicians(p); setLeaves(l);
      setDemandRows(d); setCapacity(c); setLookupTables(lt);
    } catch (err) {
      setError(err.message || "Failed to load data from API");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (loggedIn) loadAll(); }, [loggedIn]); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshSites = async () => {
    const [s, c] = await Promise.all([apiFetch("/sites/"), apiFetch(`/capacity?year=${YEAR}`)]);
    setSites(s); setCapacity(c);
  };

  const refreshPhysicians = async () => {
    const [p, c] = await Promise.all([apiFetch("/physicians/?is_active=true"), apiFetch(`/capacity?year=${YEAR}`)]);
    setPhysicians(p); setCapacity(c);
  };

  const refreshLeaves = async () => {
    const [l, c] = await Promise.all([apiFetch(`/leaves/?year=${YEAR}`), apiFetch(`/capacity?year=${YEAR}`)]);
    setLeaves(l); setCapacity(c);
  };

  const handleDemandUpdate = async (siteId, year, month, hoursRequired) => {
    try {
      await apiFetch("/demand/", {
        method: "PUT",
        body: JSON.stringify({site_id: siteId, year, month, hours_required: hoursRequired}),
      });
      const [d, c] = await Promise.all([apiFetch(`/demand/?year=${YEAR}`), apiFetch(`/capacity?year=${YEAR}`)]);
      setDemandRows(d); setCapacity(c);
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const handleError = (msg) => setError(msg || "An error occurred");

  const {title, sub} = PAGE[tab];

  if (!loggedIn) {
    return (
      <>
        <style>{CSS}</style>
        <LoginScreen onLogin={handleLogin}/>
      </>
    );
  }

  return (
    <>
      <style>{CSS}</style>
      <div className="shell">
        <aside className="sidebar">
          <div className="sb-logo">
            <div className="tag">Emergency Medicine</div>
            <div className="name">Capacity Planner</div>
            <div className="sub">Workforce · {YEAR}</div>
          </div>
          <nav className="sb-nav">
            {NAV.filter(({adminOnly})=>!adminOnly || user.role==="admin").map(({id,label,Icon})=>(
              <button key={id} className={`sb-item ${tab===id?"active":""}`} onClick={()=>setTab(id)}>
                <Icon/>{label}
                {id==="leaves"&&leaves.length>0&&<span className="sb-badge">{leaves.length}</span>}
              </button>
            ))}
          </nav>
        </aside>
        <div className="main">
          <div className="topbar">
            <div><div className="title">{title}</div><div className="sub">{sub}</div></div>
            <div style={{display:"flex",alignItems:"center",gap:16}}>
              <div className="year-chip">{YEAR}</div>
              <div className="user-chip">
                <div className="u-name">{user.name}</div>
                <div className="u-email">{user.email}</div>
              </div>
              <button className="btn sm" onClick={handleLogout}>Log out</button>
            </div>
          </div>
          <div className="content">
            <ErrorBanner message={error} onDismiss={()=>setError(null)}/>
            {loading ? <Spinner/> : (
              <>
                {tab==="dashboard"  && <Dashboard    sites={sites} physicians={physicians} leaves={leaves} capacity={capacity}/>}
                {tab==="physicians" && <PhysiciansTab sites={sites} lookupTables={lookupTables} onRefresh={refreshPhysicians} onError={handleError}/>}
                {tab==="sites"      && <SitesTab     onRefresh={refreshSites} onError={handleError}/>}
                {tab==="demand"     && <DemandTab    sites={sites} demand={demandMap} onDemandUpdate={handleDemandUpdate}/>}
                {tab==="leaves"     && <LeavesTab    leaves={leaves} physicians={physicians} onRefresh={refreshLeaves} onError={handleError}/>}
                {tab==="staffing"   && <StaffingTab  sites={sites} physicians={physicians} leaves={leaves} capacity={capacity}/>}
                {tab==="time-allocations" && <TimeAllocationsTab physicians={physicians} onRefresh={refreshPhysicians} onError={handleError}/>}
                {tab==="audit"      && user.role==="admin" && <AuditLogTab onError={handleError}/>}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
