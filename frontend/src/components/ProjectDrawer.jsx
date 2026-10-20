import { useEffect, useState } from "react";
import { api } from "../api.js";
import ScoreBadge, { money } from "./ScoreBadge.jsx";
import ProposalEditor from "./ProposalEditor.jsx";

export default function ProjectDrawer({ projectId, onClose, onChanged }) {
  const [project, setProject] = useState(null);
  const [proposal, setProposal] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    setProject(null);
    setProposal(null);
    setError("");
    api.project(projectId)
      .then((p) => { if (alive) { setProject(p); onChanged && onChanged(); } })
      .catch((e) => alive && setError(e.message));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function makeDraft() {
    setBusy(true);
    setError("");
    try {
      setProposal(await api.draft(projectId));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function ignore() {
    try {
      await api.setProjectStatus(projectId, "ignored");
      onChanged && onChanged();
      onClose();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="تفاصيل المشروع">
        <button className="close" onClick={onClose} aria-label="إغلاق">✕</button>
        {error && <p className="err">{error}</p>}
        {!project && !error && <div className="skeleton tall" />}
        {project && (
          <>
            <h2>{project.title}</h2>
            <div className="meta">
              <ScoreBadge score={project.ai_score} />
              <span>💰 {money(project)}</span>
              <span>📩 {project.proposals_count ?? "—"} عروض</span>
              {project.category && <span>🏷 {project.category}</span>}
              {project.has_my_proposal && <span className="badge mid">قدّمت عليه</span>}
            </div>
            {project.ai_summary && (
              <section className="card soft">
                <h3>ملخص الذكاء الاصطناعي</h3>
                <p>{project.ai_summary}</p>
                {project.ai_reason && <p className="hint">سبب الدرجة: {project.ai_reason}</p>}
              </section>
            )}
            <section>
              <h3>الوصف</h3>
              <p className="desc">{project.description || "لم يُسحب الوصف بعد."}</p>
            </section>
            <div className="row gap wrap">
              <a className="btn" href={project.url} target="_blank" rel="noreferrer">فتح في مستقل</a>
              <button className="btn primary" disabled={busy} onClick={makeDraft}>
                {busy ? "جارٍ الكتابة…" : proposal ? "إعادة توليد المسودة" : "✍️ اكتب عرضاً"}
              </button>
              <button className="btn" onClick={ignore}>تجاهل المشروع</button>
            </div>
            {proposal && (
              <ProposalEditor proposal={proposal} projectUrl={project.url} onChange={setProposal} />
            )}
          </>
        )}
      </aside>
    </div>
  );
}
