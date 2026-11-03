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
    <>
      <header className="app-nav">
        <Link className="app-brand" to="/">
          <span className="app-mark">D</span>DubForge
        </Link>
        <span className="app-nav-link">video localization workspace</span>
      </header>
      <main className="page-canvas">
        <div className="page-inner">
          <span className="eyebrow">studio / projects</span>
          <h1 className="page-title">
            make every voice
            <br />
            feel native.
          </h1>
          <p className="page-subtitle">
            Upload a video, review the transcript, shape the translation, and
            export a finished dub from one calm workspace.
          </p>
          <section className="surface create-card">
            <div>
              <h2>Start a new project</h2>
              <p>
                Give your next localization pass a home. You can add media and
                begin processing immediately.
              </p>
            </div>
            <form className="create-form" onSubmit={handleCreate}>
              <input
                className="text-input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Project name"
                required
              />
              <button
                className="button button-primary"
                type="submit"
                disabled={creating}
              >
                {creating ? "Creating…" : "Create project"}
              </button>
            </form>
          </section>
          {createError && (
            <p className="alert" role="alert">
              {createError}
            </p>
          )}
          <div className="section-heading">
            <h2>Your projects</h2>
            <p>
              {loading
                ? "Loading…"
                : `${projects.length} workspace${projects.length === 1 ? "" : "s"}`}
            </p>
          </div>
          {error && (
            <p className="alert" role="alert">
              {error}
            </p>
          )}
          {!loading && !error && projects.length === 0 && (
            <div className="surface empty-state">
              No projects yet. Create your first localization workspace above.
            </div>
          )}
          <ul className="project-grid">
            {projects.map((project) => (
              <li className="surface project-card" key={project.id}>
                <Link to={`/projects/${project.id}`}>
                  <strong>{project.name}</strong>
                  <small>
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </small>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </main>
    </>
  );
}
