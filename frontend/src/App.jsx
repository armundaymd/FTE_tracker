import { useState, useMemo, useEffect, useRef } from "react";

// ── Constants ──────────────────────────────────────────────────────────────
const LEAVE_TYPES = ["FMLA","LOA","Research Protected Time","Maternity/Paternity","Medical","Administrative","Other"];

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
const API_BASE = "http://localhost:8001/api";

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {"Content-Type": "application/json"},
    ...opts,
  });
  if (res.status === 204) return null;
  const data = await res.json();
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

// ── Small components ───────────────────────────────────────────────────────
const LeaveBadge = ({type}) => { const c=LEAVE_COLORS[type]||LEAVE_COLORS.Other; return <span className="lbadge" style={{background:c.bg,color:c.color}}>{type}</span>; };
const TypeBadge  = ({type}) => { const c=typeColor(type); return <span className="lbadge" style={{background:c.bg,color:c.color}}>{type}</span>; };
const Gap = ({val,unit=""}) => { if(val===0) return <span className="neu">0{unit}</span>; return <span className={val>0?"pos":"neg"}>{val>0?"+":""}{val}{unit}</span>; };

function Spinner() {
  return (
    <div style={{display:"flex",alignItems:"center",justifyContent:"center",padding:"60px",color:"var(--muted)"}}>
      <svg className="spin" width={28} height={28} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
      </svg>
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
function PhysiciansTab({physicians, sites, lookupTables, onRefresh, onError}) {
  const [adding,    setAdding]    = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [filter,    setFilter]    = useState("All");
  const [editingId, setEditingId] = useState(null);

  const blankForm = {
    life_no: "", last_name: "", first_name: "",
    provider_type_id: null, yearly_hours: 1440, clinical_pct: 1.0,
    core_site_id: null, notes: "", assignments: [], roles: [],
  };
  const [form, setForm] = useState(blankForm);

  const startEdit = (p) => {
    setEditingId(p.id);
    setForm({
      life_no: p.life_no||"", last_name: p.last_name, first_name: p.first_name,
      provider_type_id: p.provider_type_id, yearly_hours: p.yearly_hours, clinical_pct: p.clinical_pct,
      core_site_id: p.core_site_id, notes: p.notes||"",
      assignments: p.assignments.map(a=>({id: a.id, site_id: a.site_id, fte_fraction: a.fte_fraction})),
      roles: p.roles.map(r=>({id: r.id, role_type_id: r.role_type_id, hours_credit: r.hours_credit})),
    });
    setAdding(true);
  };

  const cancelForm = () => {
    setAdding(false);
    setEditingId(null);
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
      await apiFetch(`/physicians/${physicianId}/assignments/${a.id}`, {
        method: "PUT", body: JSON.stringify({site_id: a.site_id, fte_fraction: a.fte_fraction}),
      });
    }
    for (const a of current.filter(a=>!a.id)) {
      await apiFetch(`/physicians/${physicianId}/assignments`, {
        method: "POST", body: JSON.stringify({site_id: a.site_id, fte_fraction: a.fte_fraction}),
      });
    }
  };

  // Roles have no PUT endpoint — changed rows are deleted and re-created.
  const syncRoles = async (physicianId, original, current) => {
    const origById = new Map(original.map(r=>[r.id, r]));
    const currentIds = new Set(current.filter(r=>r.id).map(r=>r.id));
    const changed = current.filter(r => {
      if (!r.id) return false;
      const o = origById.get(r.id);
      return o && (o.role_type_id !== r.role_type_id || o.hours_credit !== r.hours_credit);
    });
    for (const r of original.filter(r=>!currentIds.has(r.id))) {
      await apiFetch(`/physicians/${physicianId}/roles/${r.id}`, {method: "DELETE"});
    }
    for (const r of changed) {
      await apiFetch(`/physicians/${physicianId}/roles/${r.id}`, {method: "DELETE"});
    }
    for (const r of [...current.filter(r=>!r.id), ...changed]) {
      await apiFetch(`/physicians/${physicianId}/roles`, {
        method: "POST", body: JSON.stringify({role_type_id: r.role_type_id, hours_credit: r.hours_credit}),
      });
    }
  };

  const save = async () => {
    if (!form.last_name.trim() || !form.assignments.length) return;
    setSaving(true);
    try {
      const body = {
        ...form,
        yearly_hours: parseInt(form.yearly_hours) || 1440,
        clinical_pct: parseFloat(form.clinical_pct) || 1.0,
        core_site_id: form.core_site_id || null,
      };
      if (editingId) {
        const original = physicians.find(p => p.id === editingId);
        await apiFetch(`/physicians/${editingId}`, {
          method: "PUT",
          body: JSON.stringify({
            life_no: body.life_no, last_name: body.last_name, first_name: body.first_name,
            provider_type_id: body.provider_type_id, yearly_hours: body.yearly_hours,
            clinical_pct: body.clinical_pct, core_site_id: body.core_site_id, notes: body.notes,
          }),
        });
        await syncAssignments(editingId, original.assignments, form.assignments);
        await syncRoles(editingId, original.roles, form.roles);
      } else {
        await apiFetch("/physicians/", {method: "POST", body: JSON.stringify(body)});
      }
      cancelForm();
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const deletePhysician = async (id) => {
    try {
      await apiFetch(`/physicians/${id}`, {method: "DELETE"});
      await onRefresh();
    } catch (err) {
      onError(err.message);
    }
  };

  const clinHrs = p => Math.round(p.yearly_hours * parseFloat(p.clinical_pct || 0));
  const roleHrs = p => p.roles.reduce((s, r) => s + (r.hours_credit || 0), 0);

  const filterOptions = ["All","MD/DO","APP","Fellows"];
  const filtered = physicians.filter(p => {
    const n = p.provider_type?.name || "";
    if (filter === "MD/DO")   return ["MD","DO"].includes(n);
    if (filter === "APP")     return ["PA","NP"].includes(n);
    if (filter === "Fellows") return n.startsWith("Fellow");
    return true;
  });

  return (
    <div>
      {!adding && (
        <div style={{display:"flex",gap:8,marginBottom:16,alignItems:"center"}}>
          <button className="btn primary" onClick={()=>setAdding(true)}><IcoPlus/> Add provider</button>
          <div className="seg" style={{marginBottom:0}}>
            {filterOptions.map(f=><button key={f} className={`seg-btn ${filter===f?"active":""}`} onClick={()=>setFilter(f)}>{f}</button>)}
          </div>
          <span style={{fontSize:12,color:"var(--muted)",marginLeft:4}}>{filtered.length} providers</span>
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
              <button className="btn sm danger" onClick={()=>rmAssign(i)}><IcoTrash/></button>
            </div>
          ))}
          <button className="btn sm" style={{marginTop:8}} onClick={addAssign}><IcoPlus/> Add site</button>

          <div className="form-row" style={{marginTop:16}}>
            <button className="btn primary" onClick={save} disabled={saving}>{editingId ? "Save changes" : "Save provider"}</button>
            <button className="btn" onClick={cancelForm}>Cancel</button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-title">Provider roster — {filtered.length}{filter!=="All"?` ${filter}`:""} of {physicians.length} total</div>
        {filtered.length===0 ? <div className="empty">No providers match this filter.</div> : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead><tr>
                <th>Life No</th><th>Name</th><th>Type</th><th>FTE</th>
                <th className="r">1.0 FTE hrs</th><th className="r">Clin hrs</th><th className="r">Role hrs</th>
                <th>Roles</th><th>Core</th><th>Sites</th><th>Notes</th><th></th>
              </tr></thead>
              <tbody>
                {filtered.map(p => {
                  const coreSite = sites.find(s => s.id === p.core_site_id);
                  return (
                    <tr key={p.id}>
                      <td className="mono muted">{p.life_no||"—"}</td>
                      <td className="bold">{p.last_name}, {p.first_name}</td>
                      <td><TypeBadge type={p.provider_type?.name||""}/></td>
                      <td className="mono">{parseFloat(p.total_fte||0).toFixed(2)}</td>
                      <td className="r mono">{p.yearly_hours}</td>
                      <td className="r mono" style={{color:"var(--green)"}}>{clinHrs(p)}</td>
                      <td className="r mono" style={{color:"var(--muted)"}}>{roleHrs(p)}</td>
                      <td>{p.roles.map((r,i)=><span key={i} className="rtag">{r.role_type?.name||r.custom_title||"Role"} ({r.hours_credit}h)</span>)}</td>
                      <td>{coreSite?<span className="stag">{coreSite.name}</span>:"—"}</td>
                      <td>{p.assignments.map((a,i)=>{const s=sites.find(x=>x.id===a.site_id);return <span key={i} className="stag">{s?.name||"?"} {a.fte_fraction}</span>;})}</td>
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

// ── Sites ──────────────────────────────────────────────────────────────────
function SitesTab({sites, onRefresh, onError}) {
  const [name,   setName]   = useState("");
  const [saving, setSaving] = useState(false);

  const add = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await apiFetch("/sites/", {method: "POST", body: JSON.stringify({name: name.trim(), areas: []})});
      setName("");
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const removeSite = async (id) => {
    try {
      await apiFetch(`/sites/${id}`, {method: "DELETE"});
      await onRefresh();
    } catch (err) {
      onError(err.message);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="card-title">Add site</div>
        <div className="form-row">
          <div className="field"><label>Site name</label><input type="text" value={name} placeholder="e.g. MSH" onChange={e=>setName(e.target.value)} onKeyDown={e=>e.key==="Enter"&&add()}/></div>
          <button className="btn primary" onClick={add} disabled={saving}><IcoPlus/> Add site</button>
        </div>
      </div>
      <div className="card">
        <div className="card-title">Clinical sites — {sites.length}</div>
        {sites.length===0 ? <div className="empty">No sites added.</div> : (
          <table className="tbl">
            <thead><tr><th>Site name</th><th>Areas</th><th></th></tr></thead>
            <tbody>
              {sites.map(s=>(
                <tr key={s.id}>
                  <td className="bold">{s.name}</td>
                  <td>{(s.areas||[]).map((a,i)=><span key={i} className="rtag">{a.name}</span>)}</td>
                  <td style={{textAlign:"right"}}>
                    <button className="btn sm danger" onClick={()=>removeSite(s.id)}><IcoTrash/> Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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

// ── Leaves ─────────────────────────────────────────────────────────────────
const BLANK_LEAVE_FORM = {physician_id:"",leave_type:LEAVE_TYPES[0],start_date:"",end_date:"",notes:""};

function LeavesTab({leaves, physicians, onRefresh, onError}) {
  const [form,      setForm]      = useState(BLANK_LEAVE_FORM);
  const [editingId, setEditingId] = useState(null);
  const [saving,    setSaving]    = useState(false);

  const startEdit = (l) => {
    setEditingId(l.id);
    setForm({physician_id: l.physician_id, leave_type: l.leave_type, start_date: l.start_date, end_date: l.end_date, notes: l.notes||""});
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(BLANK_LEAVE_FORM);
  };

  const save = async () => {
    if (!form.physician_id || !form.start_date || !form.end_date) return;
    setSaving(true);
    try {
      if (editingId) {
        await apiFetch(`/leaves/${editingId}`, {method: "PUT", body: JSON.stringify(form)});
        setEditingId(null);
      } else {
        await apiFetch("/leaves/", {method: "POST", body: JSON.stringify(form)});
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
            <select value={form.physician_id} onChange={e=>setForm(f=>({...f,physician_id:e.target.value}))} style={{minWidth:190}}>
              <option value="">Select provider…</option>
              {physicians.map(p=><option key={p.id} value={p.id}>{p.last_name}, {p.first_name} ({p.provider_type?.name||""})</option>)}
            </select>
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
              <thead><tr><th>Provider</th><th>Type</th><th>Leave</th><th>Start</th><th>End</th><th className="r">Days</th><th>Notes</th><th></th></tr></thead>
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

// ── App shell ──────────────────────────────────────────────────────────────
const NAV = [
  {id:"dashboard",label:"Dashboard",Icon:IcoDash},
  {id:"physicians",label:"Providers",Icon:IcoUsers},
  {id:"sites",label:"Sites",Icon:IcoSite},
  {id:"demand",label:"Monthly demand",Icon:IcoChart},
  {id:"leaves",   label:"Leaves",         Icon:IcoLeave},
  {id:"staffing", label:"Staffing",        Icon:IcoStaff},
];
const PAGE = {
  dashboard: {title:"Dashboard",sub:"Pre-scheduling capacity overview"},
  physicians:{title:"Providers",sub:"MD, DO, PA, NP, and Fellows"},
  sites:     {title:"Sites",sub:"Clinical sites"},
  demand:    {title:"Monthly demand",sub:"Required clinical hours per site per month"},
  leaves:    {title:"Leave events",   sub:"FMLA, LOA, research protected time, and other absences"},
  staffing:  {title:"Staffing Plan",  sub:"Annual provider hours by site — Physicians · APPs · Fellows"},
};

export default function App() {
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
        apiFetch("/physicians/"),
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

  useEffect(() => { loadAll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const refreshSites = async () => {
    const [s, c] = await Promise.all([apiFetch("/sites/"), apiFetch(`/capacity?year=${YEAR}`)]);
    setSites(s); setCapacity(c);
  };

  const refreshPhysicians = async () => {
    const [p, c] = await Promise.all([apiFetch("/physicians/"), apiFetch(`/capacity?year=${YEAR}`)]);
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
            {NAV.map(({id,label,Icon})=>(
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
            <div className="year-chip">{YEAR}</div>
          </div>
          <div className="content">
            <ErrorBanner message={error} onDismiss={()=>setError(null)}/>
            {loading ? <Spinner/> : (
              <>
                {tab==="dashboard"  && <Dashboard    sites={sites} physicians={physicians} leaves={leaves} capacity={capacity}/>}
                {tab==="physicians" && <PhysiciansTab physicians={physicians} sites={sites} lookupTables={lookupTables} onRefresh={refreshPhysicians} onError={handleError}/>}
                {tab==="sites"      && <SitesTab     sites={sites} onRefresh={refreshSites} onError={handleError}/>}
                {tab==="demand"     && <DemandTab    sites={sites} demand={demandMap} onDemandUpdate={handleDemandUpdate}/>}
                {tab==="leaves"     && <LeavesTab    leaves={leaves} physicians={physicians} onRefresh={refreshLeaves} onError={handleError}/>}
                {tab==="staffing"   && <StaffingTab  sites={sites} physicians={physicians} leaves={leaves} capacity={capacity}/>}
              </>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
