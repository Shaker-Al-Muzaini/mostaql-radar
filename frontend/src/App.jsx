import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import ProjectCard from "./components/ProjectCard.jsx";

const POLL_MS = 15000;

export default function App() {
  const [data, setData] = useState({ items: [], interval_min: 3, show_minutes: 10, running: false });
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [tick, setTick] = useState(Date.now());
  const fetchedAt = useRef(Date.now());

  async function load() {
    try {
      const d = await api.recent();
      fetchedAt.current = Date.now();
      setData(d);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoaded(true);
    }
  }

  useEffect(() => {
    load();
    const poll = setInterval(load, POLL_MS);
    const clockTimer = setInterval(() => setTick(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(clockTimer);
    };
  }, []);

  // العدّ التنازلي محلياً بين كل طلبين، وتختفي البطاقة فور انتهاء وقتها
  const elapsed = Math.floor((tick - fetchedAt.current) / 1000);
  const items = data.items.map((p) => ({ p, left: p.seconds_left - elapsed })).filter((x) => x.left > 0);

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <span className="dot" />
          رادار مستقل
        </div>
        <div className="live">
          {error ? "انقطع الاتصال بالخادم" : data.running ? "يفحص الآن…" : `مباشر · فحص كل ${data.interval_min} دقائق`}
        </div>
      </header>

      <main>
        {error && <div className="alert">{error}</div>}

        {items.length > 0 ? (
          <section className="list">
            {items.map(({ p, left }) => (
              <ProjectCard key={p.id} p={p} left={left} />
            ))}
          </section>
        ) : (
          loaded && (
            <section className="empty">
              <div className="radar"><i /></div>
              <h2>لا مشاريع جديدة الآن</h2>
              <p>يظهر كل مشروع جديد هنا لمدة {data.show_minutes} دقائق ثم يختفي تلقائياً.</p>
            </section>
          )
        )}
      </main>
    </div>
  );
}
