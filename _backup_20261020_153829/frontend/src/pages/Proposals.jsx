import { Fragment, useEffect, useState } from "react";
import { api } from "../api.js";
import ProposalEditor, { STATUS_LABEL } from "../components/ProposalEditor.jsx";

export default function Proposals({ version }) {
  const [status, setStatus] = useState("");
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    setError("");
    api.proposals(status)
      .then((r) => alive && setRows(r))
      .catch((e) => alive && setError(e.message));
    return () => { alive = false; };
  }, [status, version, tick]);

  return (
    <section className="proposals">
      <div className="row between">
        <h2>سجل العروض</h2>
        <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="فلتر الحالة">
          <option value="">كل الحالات</option>
          {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {error && (
        <div className="card">
          <p className="err">تعذّر التحميل: {error}</p>
          <button className="btn" onClick={() => setTick((t) => t + 1)}>إعادة المحاولة</button>
        </div>
      )}
      {!rows && !error && <div className="skeleton tall" />}
      {rows && rows.length === 0 && (
        <div className="card empty">لا عروض بعد. افتح مشروعاً واضغط «اكتب عرضاً».</div>
      )}
      {rows && rows.length > 0 && (
        <div className="table card">
          <table>
            <thead>
              <tr><th>المشروع</th><th>الحالة</th><th>المبلغ</th><th>المدة</th><th>التاريخ</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.id}>
                  <tr className="clickable" onClick={() => setOpenId(openId === r.id ? null : r.id)}>
                    <td>{r.project_title}</td>
                    <td><span className={`status ${r.status}`}>{STATUS_LABEL[r.status]}</span></td>
                    <td>{r.bid_amount ? `${r.bid_amount}$` : "—"}</td>
                    <td>{r.duration_days ? `${r.duration_days} يوم` : "—"}</td>
                    <td>{new Date(r.created_at + "Z").toLocaleDateString("ar-EG")}</td>
                  </tr>
                  {openId === r.id && (
                    <tr>
                      <td colSpan={5}>
                        <ProposalEditor proposal={r} projectUrl={r.project_url}
                                        onChange={() => setTick((t) => t + 1)} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
