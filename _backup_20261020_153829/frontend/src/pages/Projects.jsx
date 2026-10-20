import { useEffect, useState } from "react";
import { api } from "../api.js";
import ScoreBadge, { money } from "../components/ScoreBadge.jsx";
import ProjectDrawer from "../components/ProjectDrawer.jsx";

const STATUSES = [
  ["", "كل الحالات"],
  ["new", "جديد"],
  ["seen", "تم الاطلاع"],
  ["applied", "مقدَّم عليه"],
  ["ignored", "متجاهَل"],
];

const DEFAULTS = { q: "", category: "", min_score: 0, min_budget: 0, status: "", hide_applied: true };

export default function Projects({ version }) {
  const [filters, setFilters] = useState(DEFAULTS);
  const [debounced, setDebounced] = useState(DEFAULTS);
  const [rows, setRows] = useState(null);
  const [cats, setCats] = useState([]);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  const [tick, setTick] = useState(0);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(filters), 300);
    return () => clearTimeout(t);
  }, [filters]);

  useEffect(() => {
    let alive = true;
    setError("");
    api.projects(debounced)
      .then((r) => alive && setRows(r))
      .catch((e) => alive && setError(e.message));
    api.categories().then((c) => alive && setCats(c)).catch(() => {});
    return () => { alive = false; };
  }, [debounced, version, tick]);

  const set = (k, v) => setFilters((f) => ({ ...f, [k]: v }));

  return (
    <div className="layout">
      <button className="btn filters-toggle" onClick={() => setShowFilters((s) => !s)}>
        {showFilters ? "إخفاء الفلاتر" : "إظهار الفلاتر"}
      </button>
      <aside className={showFilters ? "filters open" : "filters"}>
        <h3>الفلاتر</h3>
        <label>
          بحث
          <input value={filters.q} onChange={(e) => set("q", e.target.value)} placeholder="كلمة في العنوان أو الوصف" />
        </label>
        <label>
          التصنيف
          <select value={filters.category} onChange={(e) => set("category", e.target.value)}>
            <option value="">الكل</option>
            {cats.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label>
          أدنى درجة: <b>{filters.min_score}</b>
          <input type="range" min="0" max="100" step="5" value={filters.min_score}
                 onChange={(e) => set("min_score", Number(e.target.value))} />
        </label>
        <label>
          أدنى ميزانية ($)
          <input type="number" min="0" value={filters.min_budget || ""}
                 onChange={(e) => set("min_budget", Number(e.target.value) || 0)} />
        </label>
        <label>
          الحالة
          <select value={filters.status} onChange={(e) => set("status", e.target.value)}>
            {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={filters.hide_applied} onChange={(e) => set("hide_applied", e.target.checked)} />
          إخفاء ما قدّمت عليه
        </label>
        <button className="btn" onClick={() => setFilters(DEFAULTS)}>إعادة الضبط</button>
      </aside>

      <section className="list" aria-live="polite">
        {error && (
          <div className="card">
            <p className="err">تعذّر تحميل المشاريع: {error}</p>
            <button className="btn" onClick={() => setTick((t) => t + 1)}>إعادة المحاولة</button>
          </div>
        )}
        {!rows && !error && [1, 2, 3, 4].map((i) => <div key={i} className="skeleton" />)}
        {rows && rows.length === 0 && (
          <div className="card empty">لا مشاريع تطابق الفلاتر. جرّب «تحديث الآن» أو خفّف الفلاتر.</div>
        )}
        {rows && rows.map((p) => (
          <article key={p.id} className={`card project ${p.status}`} onClick={() => setOpenId(p.id)}
                   tabIndex={0} onKeyDown={(e) => e.key === "Enter" && setOpenId(p.id)}>
            <div className="row between">
              <h3>{p.title}</h3>
              <ScoreBadge score={p.ai_score} />
            </div>
            <div className="meta">
              <span>💰 {money(p)}</span>
              <span>📩 {p.proposals_count ?? "—"} عروض</span>
              {p.category && <span>🏷 {p.category}</span>}
              {p.posted_text && <span>🕒 {p.posted_text}</span>}
              {p.status === "new" && <span className="badge new">جديد</span>}
              {p.has_my_proposal && <span className="badge mid">قدّمت عليه</span>}
            </div>
            {p.ai_summary && <p className="summary">{p.ai_summary}</p>}
          </article>
        ))}
      </section>

      {openId && (
        <ProjectDrawer projectId={openId} onClose={() => setOpenId(null)} onChanged={() => setTick((t) => t + 1)} />
      )}
    </div>
  );
}
