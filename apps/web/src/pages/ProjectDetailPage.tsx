import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getProject, type Project } from "../api/client";

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getProject(id)
      .then(setProject)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <main>
      <p>
        <Link to="/">&larr; Back to projects</Link>
      </p>
      {loading && <p>Loading project…</p>}
      {error && <p role="alert">{error}</p>}
      {project && (
        <>
          <h1>{project.name}</h1>
          <p>Created {new Date(project.created_at).toLocaleString()}</p>
        </>
      )}
    </main>
  );
}
