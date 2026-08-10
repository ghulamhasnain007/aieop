import { useState } from "react";
import ChatPanel from "./components/ChatPanel.jsx";
import IntegrationHealth from "./components/IntegrationHealth.jsx";
import ApprovalCenter from "./components/ApprovalCenter.jsx";
import Overview from "./components/Overview.jsx";
import KnowledgeBase from "./components/KnowledgeBase.jsx";
import Incidents from "./components/Incidents.jsx";
import ProjectSwitcher from "./components/ProjectSwitcher.jsx";
import { useAppState } from "./context/AppStateContext.jsx";

const NAV = [
  { id: "overview", label: "Overview", title: "Project Overview", subtitle: "health score & risk signals" },
  { id: "chat", label: "Chat", title: "Coordinator", subtitle: "natural-language interface" },
  { id: "incidents", label: "Incidents", title: "Incident Center", subtitle: "timeline, dependencies, tech debt" },
  { id: "knowledge", label: "Knowledge Base", title: "Knowledge Base", subtitle: "RAG-grounded document search" },
  { id: "approvals", label: "Approvals", title: "Approval Center", subtitle: "human-in-the-loop actions" },
  { id: "integrations", label: "Integrations", title: "Integration health", subtitle: "adapter connectivity" },
];

const ROLES = [
  "system_admin", "engineering_manager", "tech_lead",
  "developer", "qa_engineer", "devops_engineer", "viewer",
];

const PANELS = {
  overview: Overview,
  chat: ChatPanel,
  incidents: Incidents,
  knowledge: KnowledgeBase,
  approvals: ApprovalCenter,
  integrations: IntegrationHealth,
};

export default function App() {
  const [view, setView] = useState("overview");
  const { role, setRole } = useAppState();
  const current = NAV.find((n) => n.id === view);
  const Panel = PANELS[view];

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
          All 6 phases · v1.0
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="topbar-title">
            {current.title}
            <span>{current.subtitle}</span>
          </div>
          <div className="topbar-controls">
            <ProjectSwitcher />
            <select className="role-select" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
        </div>

        <Panel />
      </main>
    </div>
  );
}
