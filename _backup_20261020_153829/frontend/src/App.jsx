import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import Projects from "./pages/Projects.jsx";
import Proposals from "./pages/Proposals.jsx";

function RefreshButton({ onDone }) {
  const [state, setState] = useState({ running: false, stage: "", error: "", info: "" });
  const timer = useRef(null);

  const poll = useCallback(async () => {
    try {
      const { running, run } = await api.refreshStatus();
      if (running) {
        setState({ running: true, stage: run?.stage || "جارٍ العمل…", error: "", info: "" });
        timer.current = setTimeout(poll, 2000);
        return;
      }
      if (run?.status === "error") {
        setState({ running: false, stage: "", error: run.error || "فشل التحديث", info: "" });
      } else if (run?.status === "done") {
        setState({
          running: false, stage: "", error: "",
          info: `جديد: ${run.new_count} · أُرسل: ${run.notified_count}`,
        });
      } else {
        setState((s) => ({ ...s, running: false }));
      }
      onDone();
    } catch (e) {
      setState({ running: false, stage: "", error: e.message, info: "" });
    }
  }, [onDone]);

  useEffect(() => () => clearTimeout(timer.current), []);

  async function start() {
    setState({ running: true, stage: "بدء التحديث…", error: "", info: "" });
    try {
      await api.refresh();
      timer.current = setTimeout(poll, 1500);
    } catch (e) {
      setState({ running: false, stage: "", error: e.message, info: "" });
    }
  }

  return (
    <div className="refresh">
      <button className="btn primary" onClick={start} disabled={state.running}>
        {state.running ? "جارٍ التحديث…" : "تحديث الآن"}
      </button>
      <span className="refresh-msg" role="status" aria-live="polite">
        {state.running && state.stage}
        {state.error && <span className="err">{state.error}</span>}
        {!state.running && !state.error && state.info}
      </span>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("projects");
  const [version, setVersion] = useState(0);
  const bump = useCallback(() => setVersion((v) => v + 1), []);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">📡 رادار مستقل</div>
        <nav>
          <button className={tab === "projects" ? "tab active" : "tab"} onClick={() => setTab("projects")}>
            المشاريع
          </button>
          <button className={tab === "proposals" ? "tab active" : "tab"} onClick={() => setTab("proposals")}>
            العروض
          </button>
        </nav>
        <RefreshButton onDone={bump} />
      </header>
      <main>
        {tab === "projects" ? <Projects version={version} /> : <Proposals version={version} />}
      </main>
    </div>
  );
}
