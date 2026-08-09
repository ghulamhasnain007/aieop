import { useState } from "react";
import ChatPanel from "./components/ChatPanel.jsx";
import IntegrationHealth from "./components/IntegrationHealth.jsx";

const NAV = [
  { id: "chat", label: "Chat" },
  { id: "integrations", label: "Integrations" },
];

const ROLES = [
  "system_admin", "engineering_manager", "tech_lead",
  "developer", "qa_engineer", "devops_engineer", "viewer",
];

export default function App() {
  const [view, setView] = useState("chat");
  const [role, setRole] = useState("developer");

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" />
          <span className="brand-name">AIEOP</span>
        </div>
        <div className="brand-sub">engineering operations hub</div>

        {NAV.map((n) => (
          <div
            key={n.id}
            className={`nav-item ${view === n.id ? "active" : ""}`}
            onClick={() => setView(n.id)}
          >
            <span className="nav-dot" />
            {n.label}
          </div>
        ))}

        <div className="sidebar-footer">
          Phase 1–4 slice · v0.1
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="topbar-title">
            {view === "chat" ? "Coordinator" : "Integration health"}
            <span>{view === "chat" ? "natural-language interface" : "adapter connectivity"}</span>
          </div>
          <select className="role-select" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>

        {view === "chat" ? <ChatPanel projectId={null} role={role} /> : <IntegrationHealth />}
      </main>
    </div>
  );
}
