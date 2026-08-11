import { useState } from "react";
import { useAppState } from "../context/AppStateContext.jsx";

export default function ProjectSwitcher() {
  const { projects, projectId, setProjectId, refreshProjects, loadingProjects } = useAppState();
  const [seeding, setSeeding] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [showSync, setShowSync] = useState(false);
  const [repoInput, setRepoInput] = useState("");
  const [syncMsg, setSyncMsg] = useState("");

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

  async function createProject(name) {
    const resp = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await resp.json();
    await refreshProjects();
    return data.id;
  }

  async function createProjectFromInput() {
    if (!newName.trim()) return;
    const id = await createProject(newName.trim());
    setProjectId(id);
    setNewName("");
    setCreating(false);
  }

  async function syncGithubRepo() {
    if (!repoInput.trim()) return;
    setSyncing(true);
    setSyncMsg("");
    try {
      let targetProjectId = projectId;
      if (!targetProjectId) {
        targetProjectId = await createProject(repoInput.trim());
        setProjectId(targetProjectId);
      }
      const resp = await fetch("/api/github/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: targetProjectId, repo: repoInput.trim() }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setSyncMsg(data.detail || "Sync failed");
      } else {
        setSyncMsg(
          `Synced ${data.repo}: ${data.commits} commits, ${data.pull_requests} PRs, ` +
          `${data.issues} issues, ${data.builds} builds, ${data.documents} doc(s)`
        );
        setRepoInput("");
        setShowSync(false);
      }
    } catch {
      setSyncMsg("Sync failed - is the backend reachable?");
    } finally {
      setSyncing(false);
    }
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
            onKeyDown={(e) => e.key === "Enter" && createProjectFromInput()}
          />
          <button className="icon-btn" onClick={createProjectFromInput}>Create</button>
          <button className="icon-btn" onClick={() => setCreating(false)}>Cancel</button>
        </>
      ) : showSync ? (
        <>
          <input
            className="role-select"
            style={{ minWidth: 200 }}
            autoFocus
            placeholder="owner/repo (e.g. facebook/react)"
            value={repoInput}
            onChange={(e) => setRepoInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && syncGithubRepo()}
          />
          <button className="icon-btn" onClick={syncGithubRepo} disabled={syncing}>
            {syncing ? "Syncing…" : "Sync"}
          </button>
          <button className="icon-btn" onClick={() => setShowSync(false)}>Cancel</button>
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
          <button className="icon-btn" onClick={() => setShowSync(true)}>Sync GitHub repo</button>
          <button className="icon-btn" onClick={seedDemo} disabled={seeding}>
            {seeding ? "Seeding…" : "Load demo data"}
          </button>
        </>
      )}
      {syncMsg && <span style={{ fontSize: 11, color: "var(--text-faint)", marginLeft: 4 }}>{syncMsg}</span>}
    </div>
  );
}
