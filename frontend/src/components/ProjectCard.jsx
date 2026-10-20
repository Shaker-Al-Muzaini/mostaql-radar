function money(p) {
  if (p.budget_min === null || p.budget_min === undefined) return "ميزانية غير محددة";
  if (p.budget_min === p.budget_max) return `${p.budget_min}$`;
  return `${p.budget_min}–${p.budget_max}$`;
}

function clock(sec) {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function level(score) {
  if (score === null || score === undefined) return "none";
  return score >= 80 ? "high" : score >= 60 ? "mid" : "low";
}

export default function ProjectCard({ p, left }) {
  const pct = Math.max(0, Math.min(100, (left / p.total_seconds) * 100));
  const lv = level(p.ai_score);
  return (
    <article className={`card ${lv} ${left < 60 ? "ending" : ""}`}>
      <div className="ring" style={{ "--p": p.ai_score ?? 0 }} aria-label={`التقييم ${p.ai_score ?? "غير متاح"}`}>
        <span>{p.ai_score ?? "—"}</span>
      </div>
      <div className="body">
        <h2 className="title">{p.title}</h2>
        <div className="meta">
          <span>💰 {money(p)}</span>
          <span>📩 {p.proposals_count ?? "—"} عروض</span>
          {p.category && <span>🏷 {p.category}</span>}
          {p.posted_text && <span>🕒 {p.posted_text}</span>}
        </div>
        {p.ai_summary && <p className="summary">{p.ai_summary}</p>}
        <a className="open" href={p.url} target="_blank" rel="noopener noreferrer">
          افتح في مستقل ↗
        </a>
      </div>
      <div className="timer" title="الوقت المتبقي لظهور المشروع">
        <span>{clock(left)}</span>
        <div className="bar"><i style={{ width: `${pct}%` }} /></div>
      </div>
    </article>
  );
}
