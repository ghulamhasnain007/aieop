import { useEffect, useState } from "react";

const RISK_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };

export default function ApprovalCenter({ role }) {
  const [pending, setPending] = useState([]);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const [p, a] = await Promise.all([
        fetch("/api/actions/pending").then((r) => r.json()),
        fetch("/api/audit?limit=20").then((r) => r.json()),
      ]);
      setPending(p.sort((x, y) => (RISK_ORDER[x.risk_level] ?? 9) - (RISK_ORDER[y.risk_level] ?? 9)));
      setAudit(a);
    } catch {
      setPending([]);
      setAudit([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function act(id, endpoint) {
    setBusyId(id);
    try {
      await fetch(`/api/actions/${id}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approver_label: role }),
      });
      await load();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="panel-body">
      <div className="evidence-trail-label" style={{ marginBottom: 14 }}>
        Pending AI actions — approve, reject, or inspect evidence
      </div>

      {loading ? (
        <div style={{ color: "var(--text-faint)" }}>Loading…</div>
      ) : pending.length === 0 ? (
        <div style={{ color: "var(--text-faint)" }}>Nothing awaiting approval right now.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 28 }}>
          {pending.map((a) => (
            <div className="integration-card" key={a.id}>
              <div className="integration-card-head">
                <span className="integration-name">
                  {a.agent_name} · {a.action_type.replace(/_/g, " ")}
                </span>
                <span className={`pill risk-${a.risk_level}`}>{a.risk_level}</span>
              </div>
              <div className="integration-detail" style={{ marginBottom: 10 }}>
                {JSON.stringify(a.payload)}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="send-btn"
                  disabled={busyId === a.id}
                  onClick={() => act(a.id, "approve")}
                >
                  Approve
                </button>
                <button
                  className="suggestion-chip"
                  disabled={busyId === a.id}
                  onClick={() => act(a.id, "reject")}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="evidence-trail-label" style={{ marginBottom: 14 }}>
        Recent audit trail
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {audit.map((e) => (
          <div key={e.id} className="meta-row" style={{ borderBottom: "1px solid var(--border-soft)", paddingBottom: 8 }}>
            <span className="pill">{e.result?.startsWith("failed") ? "failed" : e.result}</span>
            <span>{e.actor}</span>
            <span>→</span>
            <span>{e.action}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
