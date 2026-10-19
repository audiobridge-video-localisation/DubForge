import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createProject, listProjects, type Project } from "../api/client";

export function ProjectListPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const project = await createProject(name);
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setCreateError((err as Error).message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <main>
      <h1>DubForge</h1>

      <form onSubmit={handleCreate}>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Project name"
          required
        />
        <button type="submit" disabled={creating}>
          {creating ? "Creating…" : "Create project"}
        </button>
      </form>
      {createError && <p role="alert">{createError}</p>}

      <h2>Projects</h2>
      {loading && <p>Loading projects…</p>}
      {error && <p role="alert">{error}</p>}
      {!loading && !error && projects.length === 0 && <p>No projects yet.</p>}
      <ul>
        {projects.map((project) => (
          <li key={project.id}>
            <Link to={`/projects/${project.id}`}>{project.name}</Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
