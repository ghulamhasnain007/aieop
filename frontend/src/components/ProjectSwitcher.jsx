import { useState } from "react";
import { useAppState } from "../context/AppStateContext.jsx";

export default function ProjectSwitcher() {
  const { projects, projectId, setProjectId, refreshProjects, loadingProjects } = useAppState();
  const [seeding, setSeeding] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  async function seedDemo() {
    setSeeding(true);
    try {
      const resp = await fetch("/api/demo/seed", { method: "POST" });
      const data = await resp.json();
      await refreshProjects();
      setProjectId(data.project_id);
    } finally {
      setSeeding(false);
    }
  }

  async function createProject() {
    if (!newName.trim()) return;
    const resp = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName.trim() }),
    });
    const data = await resp.json();
    await refreshProjects();
    setProjectId(data.id);
    setNewName("");
    setCreating(false);
  }

  return (
    <div className="project-switcher">
      {creating ? (
        <>
          <input
            className="role-select"
            style={{ minWidth: 160 }}
            autoFocus
            placeholder="Project name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createProject()}
          />
          <button className="icon-btn" onClick={createProject}>Create</button>
          <button className="icon-btn" onClick={() => setCreating(false)}>Cancel</button>
        </>
      ) : (
        <>
          <select
            className="role-select"
            value={projectId || ""}
            onChange={(e) => setProjectId(e.target.value)}
            disabled={loadingProjects || projects.length === 0}
          >
            {projects.length === 0 && <option value="">No projects yet</option>}
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <button className="icon-btn" onClick={() => setCreating(true)}>+ New</button>
          <button className="icon-btn" onClick={seedDemo} disabled={seeding}>
            {seeding ? "Seeding…" : "Load demo data"}
          </button>
        </>
      )}
    </div>
  );
}
