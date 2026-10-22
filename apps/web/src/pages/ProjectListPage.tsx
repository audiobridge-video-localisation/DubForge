import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createProject, listProjects, type Project } from "../api/client";
import { AppShell, PageHeading } from "../components/app/AppShell";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { relativeTime } from "../lib/workflow";

export function ProjectListPage() {
  useDocumentTitle("Projects · DubForge");
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const navigate = useNavigate();

  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listProjects()
      .then((list) => {
        if (!cancelled) setProjects(list);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setCreateError("Give the project a name.");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const project = await createProject(trimmed);
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setCreateError((err as Error).message);
      setCreating(false);
    }
  }

  return (
    <AppShell>
      <PageHeading
        title="Projects"
        subtitle="Create a project, upload a video, then review the dub line by line."
      />

      <section className="card create" aria-labelledby="create-title">
        <div>
          <h2 id="create-title">New project</h2>
          <p>
            One project holds a video, its transcript, translation and exports.
          </p>
        </div>
        <form className="create-form" onSubmit={handleCreate} noValidate>
          <label className="sr-only" htmlFor="project-name">
            Project name
          </label>
          <input
            id="project-name"
            className="input"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setCreateError(null);
            }}
            placeholder="Project name"
            autoComplete="off"
            aria-invalid={createError ? true : undefined}
            aria-describedby={createError ? "create-error" : undefined}
          />
          <button className="btn btn-primary" type="submit" disabled={creating}>
            {creating ? "Creating…" : "Create project"}
          </button>
        </form>
        {createError && (
          <p
            id="create-error"
            className="inline-error create-error"
            role="alert"
          >
            {createError}
          </p>
        )}
      </section>

      <div className="list-head">
        <h2>Your projects</h2>
        <span>
          {loading
            ? "Loading…"
            : `${projects.length} project${projects.length === 1 ? "" : "s"}`}
        </span>
      </div>

      {error && (
        <div className="banner banner-danger banner-action" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setAttempt((n) => n + 1)}
          >
            Try again
          </button>
        </div>
      )}

      {loading && (
        <ul className="project-grid" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <li key={i} className="skeleton skeleton-tile" />
          ))}
        </ul>
      )}

      {!loading && !error && projects.length === 0 && (
        <div className="card empty">
          <h2>No projects yet</h2>
          <p>Name your first project above to get started.</p>
        </div>
      )}

      {projects.length > 0 && (
        <ul className="project-grid">
          {projects.map((project) => (
            <li key={project.id}>
              <Link
                className="card project-tile"
                to={`/projects/${project.id}`}
              >
                <strong>{project.name}</strong>
                <small>
                  Created {relativeTime(new Date(project.created_at))}
                </small>
                <span className="tile-open" aria-hidden="true">
                  Open ↗
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </AppShell>
  );
}
