import { useEffect, useState } from "react";
import { useAppState } from "../context/AppStateContext.jsx";

export default function Incidents() {
  const { projectId } = useAppState();
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    if (!projectId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetch(`/api/incidents?project_id=${projectId}`)
      .then((r) => r.json())
      .then(setIncidents)
      .finally(() => setLoading(false));
  }, [projectId]);

  async function selectIncident(incident) {
    setSelected(incident);
    setLoadingDetail(true);
    setDetail(null);
    try {
      const [timeline, deps, techDebt] = await Promise.all([
        fetch(`/api/incidents/${incident.id}/timeline`).then((r) => r.json()),
        incident.service_id
          ? fetch(`/api/services/${incident.service_id}/dependencies`).then((r) => r.json())
          : Promise.resolve(null),
        incident.service_id
          ? fetch(`/api/services/${incident.service_id}/tech-debt`).then((r) => r.json())
          : Promise.resolve(null),
      ]);
      setDetail({ timeline, deps, techDebt });
    } finally {
      setLoadingDetail(false);
    }
  }

  if (loading) return <div className="panel-body" style={{ color: "var(--text-faint)" }}>Loading…</div>;

  if (incidents.length === 0) {
    return (
      <div className="panel-body">
        <div className="seed-prompt">
          <div className="glyph">// NO INCIDENTS</div>
          <div>Nothing recorded for this project yet — "Load demo data" in the top bar has a live one.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel-body">
      <div className="section-title">Incidents</div>
      <div className="incident-list">
        {incidents.map((inc) => (
          <div
            className={`incident-card ${selected?.id === inc.id ? "selected" : ""}`}
            key={inc.id}
            onClick={() => selectIncident(inc)}
          >
            <div className="incident-card-head">
              <span className="incident-title">{inc.title}</span>
              <span className={`severity-badge ${inc.severity || "default"}`}>{inc.severity || "unknown"}</span>
            </div>
            <div className="integration-detail" style={{ marginTop: 6 }}>
              {inc.status} · {inc.root_cause_confidence != null ? `${Math.round(inc.root_cause_confidence * 100)}% confidence` : "no root cause yet"}
            </div>
          </div>
        ))}
      </div>

      {selected && (
        <>
          {loadingDetail ? (
            <div style={{ color: "var(--text-faint)" }}>Loading investigation…</div>
          ) : detail && (
            <>
              <div className="section-title">Timeline</div>
              {detail.timeline.events.length === 0 ? (
                <div style={{ color: "var(--text-faint)", fontSize: 12.5 }}>
                  {detail.timeline.notes?.[0] || "No timeline events available."}
                </div>
              ) : (
                detail.timeline.events.map((e, i) => (
                  <div className="timeline-item" key={i}>
                    <div className="timeline-time">
                      {new Date(e.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </div>
                    <div>
                      <div className="timeline-label">{e.label}</div>
                      <div className="timeline-detail">{e.detail}</div>
                    </div>
                  </div>
                ))
              )}

              {detail.deps && !detail.deps.unknown_service && (
                <>
                  <div className="section-title">If this service fails…</div>
                  <div style={{ fontSize: 12.5, color: "var(--text-dim)" }}>
                    {detail.deps.potentially_affected_if_this_fails.length === 0
                      ? "No other services depend on this one."
                      : `Potentially affects: ${detail.deps.potentially_affected_if_this_fails.join(", ")}`}
                  </div>
                </>
              )}

              {detail.techDebt?.flagged && (
                <>
                  <div className="section-title">Technical debt signal</div>
                  <div style={{ fontSize: 12.5, color: "var(--text-dim)" }}>{detail.techDebt.message}</div>
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
