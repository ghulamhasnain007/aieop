import { useEffect, useState } from "react";

export default function IntegrationHealth() {
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const resp = await fetch("/api/integrations");
      setIntegrations(await resp.json());
    } catch {
      setIntegrations([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="panel-body">
      <div className="evidence-trail-label" style={{ marginBottom: 14 }}>
        Adapters — auth, retrieve, normalize, events, actions, health
      </div>
      {loading ? (
        <div style={{ color: "var(--text-faint)" }}>Loading…</div>
      ) : (
        <div className="integration-grid">
          {integrations.map((it) => (
            <div className="integration-card" key={it.provider}>
              <div className="integration-card-head">
                <span className="integration-name">{it.provider.replace(/_/g, " ")}</span>
                <span className={`status-dot ${it.connected ? "connected" : "disconnected"}`} />
              </div>
              <div className="integration-detail">{it.detail}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
