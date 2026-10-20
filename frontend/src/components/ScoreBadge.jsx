export default function ScoreBadge({ score }) {
  if (score === null || score === undefined) return <span className="badge muted">— غير مقيَّم</span>;
  const level = score >= 80 ? "high" : score >= 60 ? "mid" : "low";
  const label = score >= 80 ? "مناسب جداً" : score >= 60 ? "مقبول" : "ضعيف";
  return (
    <span className={`badge ${level}`}>
      {score} · {label}
    </span>
  );
}

export function money(p) {
  if (p.budget_min === null || p.budget_min === undefined) return "غير محددة";
  if (p.budget_min === p.budget_max) return `${p.budget_min}$`;
  return `${p.budget_min}–${p.budget_max}$`;
}
