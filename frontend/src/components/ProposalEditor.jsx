import { useEffect, useState } from "react";
import { api } from "../api.js";

const STATUS_LABEL = { draft: "مسودة", approved: "معتمد", sent: "مُرسَل", rejected: "مرفوض" };
export { STATUS_LABEL };

export default function ProposalEditor({ proposal, projectUrl, onChange }) {
  const [text, setText] = useState(proposal.draft_text || "");
  const [bid, setBid] = useState(proposal.bid_amount ?? "");
  const [days, setDays] = useState(proposal.duration_days ?? "");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setText(proposal.draft_text || "");
    setBid(proposal.bid_amount ?? "");
    setDays(proposal.duration_days ?? "");
  }, [proposal.id, proposal.draft_text, proposal.bid_amount, proposal.duration_days]);

  async function act(status) {
    setBusy(true);
    setMsg("");
    try {
      const body = {
        draft_text: text,
        bid_amount: bid === "" ? null : Number(bid),
        duration_days: days === "" ? null : Number(days),
      };
      if (status) body.status = status;
      const updated = await api.patchProposal(proposal.id, body);
      setMsg(status ? `الحالة: ${STATUS_LABEL[status]}` : "تم الحفظ");
      onChange && onChange(updated);
    } catch (e) {
      setMsg(`خطأ: ${e.message}`);
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setMsg("نُسخ النص — الصقه في صفحة التقديم");
    } catch {
      setMsg("تعذّر النسخ تلقائياً، حدّد النص وانسخه يدوياً");
    }
  }

  async function toTelegram() {
    try {
      await api.proposalToTelegram(proposal.id);
      setMsg("أُرسلت المسودة إلى تيليجرام");
    } catch (e) {
      setMsg(`خطأ: ${e.message}`);
    }
  }

  return (
    <div className="editor">
      <div className="row between">
        <strong>المسودة</strong>
        <span className={`status ${proposal.status}`}>{STATUS_LABEL[proposal.status]}</span>
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={10} aria-label="نص العرض" />
      <div className="row gap">
        <label>
          المبلغ ($)
          <input type="number" min="0" value={bid} onChange={(e) => setBid(e.target.value)} />
        </label>
        <label>
          المدة (أيام)
          <input type="number" min="0" value={days} onChange={(e) => setDays(e.target.value)} />
        </label>
      </div>
      <div className="row gap wrap">
        <button className="btn" disabled={busy} onClick={() => act(null)}>حفظ</button>
        <button className="btn success" disabled={busy} onClick={() => act("approved")}>موافقة</button>
        <button className="btn danger" disabled={busy} onClick={() => act("rejected")}>رفض</button>
        <button className="btn" onClick={copy}>نسخ النص</button>
        {projectUrl && (
          <a className="btn" href={projectUrl} target="_blank" rel="noreferrer">فتح في مستقل</a>
        )}
        <button className="btn" onClick={toTelegram}>إرسال لتيليجرام</button>
        <button className="btn primary" disabled={busy} onClick={() => act("sent")}>تم الإرسال</button>
      </div>
      <p className="hint" role="status">{msg}</p>
    </div>
  );
}
