import { useEffect, useState } from "react";
import { useAppState } from "../context/AppStateContext.jsx";

export default function Overview() {
  const { projectId, projects } = useAppState();
  const [health, setHealth] = useState(null);
  const [risks, setRisks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([
      fetch(`/api/projects/${projectId}/health`).then((r) => r.json()),
      fetch(`/api/projects/${projectId}/risks`).then((r) => r.json()),
    ])
      .then(([h, r]) => {
        setHealth(h);
        setRisks(r);
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  if (!loading && projects.length === 0) {
    return (
      <div className="panel-body">
        <div className="seed-prompt">
          <div className="glyph">// NO PROJECTS YET</div>
          <div>Use "Load demo data" in the top bar to see the platform working end-to-end,<br />
            or create an empty project to start from scratch.</div>
        </div>
      </div>
    );
  }

  if (loading) {
    return <div className="panel-body" style={{ color: "var(--text-faint)" }}>Loading…</div>;
  }

  return (
    <div className="panel-body">
      <div className="score-hero">
        <div className="score-total">{health?.total ?? "—"}</div>
        <div className="score-total-label">/ 100 project health</div>
      </div>

      <div className="score-bars">
        {health && Object.entries(health.breakdown).map(([key, value]) => (
          <div className="score-bar-row" key={key}>
            <div className="score-bar-label">{key.replace(/_/g, " ")}</div>
            <div className="score-bar-track">
              <div className="score-bar-fill" style={{ width: `${value}%` }} />
            </div>
            <div className="score-bar-value">{value}</div>
          </div>
        ))}
      </div>

      <div className="section-title">Risk signals</div>
      {risks.length === 0 ? (
        <div style={{ color: "var(--text-faint)", fontSize: 12.5 }}>No risks detected right now.</div>
      ) : (
        risks.map((r, i) => (
          <div className="risk-item" key={i}>
            <span className="cat">{r.category}</span>
            <span className="msg">{r.message}</span>
            <span className={`pill risk-${r.severity}`}>{r.severity}</span>
          </div>
        ))
      )}

      {health?.notes?.length > 0 && (
        <>
          <div className="section-title">Notes</div>
          {health.notes.map((n, i) => (
            <div key={i} style={{ fontSize: 11.5, color: "var(--text-faint)", marginBottom: 4 }}>{n}</div>
          ))}
        </>
      )}
    </div>
  );
}
