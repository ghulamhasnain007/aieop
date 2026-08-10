import { createContext, useContext, useEffect, useState, useCallback } from "react";

const AppStateContext = createContext(null);

export function AppStateProvider({ children }) {
  const [role, setRole] = useState(() => localStorage.getItem("aieop_role") || "developer");
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(() => localStorage.getItem("aieop_project_id") || null);
  const [loadingProjects, setLoadingProjects] = useState(true);

  useEffect(() => {
    localStorage.setItem("aieop_role", role);
  }, [role]);

  useEffect(() => {
    if (projectId) localStorage.setItem("aieop_project_id", projectId);
  }, [projectId]);

  const refreshProjects = useCallback(async () => {
    setLoadingProjects(true);
    try {
      const resp = await fetch("/api/projects");
      const data = await resp.json();
      setProjects(data);
      // If nothing selected yet, or the stored selection no longer exists, pick the first one.
      setProjectId((current) => {
        if (current && data.some((p) => p.id === current)) return current;
        return data[0]?.id ?? null;
      });
      return data;
    } catch {
      setProjects([]);
      return [];
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  useEffect(() => {
    refreshProjects();
  }, [refreshProjects]);

  const project = projects.find((p) => p.id === projectId) || null;

  return (
    <AppStateContext.Provider
      value={{ role, setRole, projects, projectId, setProjectId, project, loadingProjects, refreshProjects }}
    >
      {children}
    </AppStateContext.Provider>
  );
}

export function useAppState() {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState must be used within AppStateProvider");
  return ctx;
}
