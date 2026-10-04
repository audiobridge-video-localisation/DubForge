import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getProject,
  retryJob,
  uploadMedia,
  type MediaWithJob,
  type Project,
} from "../api/client";

const POLL_INTERVAL_MS = 3000;

function isInFlight(item: MediaWithJob): boolean {
  return item.job.status === "pending" || item.job.status === "processing";
}

function formatTimestamp(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [media, setMedia] = useState<MediaWithJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    getProject(id)
      .then((detail) => {
        setProject(detail);
        setMedia(detail.media);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!id || !media.some(isInFlight)) return;

    const interval = setInterval(() => {
      getProject(id).then((detail) => setMedia(detail.media));
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [id, media]);

  async function handleUpload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!id) return;
    const form = event.currentTarget;
    const input = form.elements.namedItem("file") as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);
    try {
      const result = await uploadMedia(id, file);
      setMedia((current) => [result, ...current]);
      form.reset();
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function handleRetry(jobId: string) {
    const updatedJob = await retryJob(jobId);
    setMedia((current) =>
      current.map((item) =>
        item.job.id === jobId ? { ...item, job: updatedJob } : item,
      ),
    );
  }

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

          <h2>Upload video</h2>
          <form onSubmit={handleUpload}>
            <input type="file" name="file" accept="video/*" required />
            <button type="submit" disabled={uploading}>
              {uploading ? "Uploading…" : "Upload"}
            </button>
          </form>
          {uploadError && <p role="alert">{uploadError}</p>}

          <h2>Media</h2>
          {media.length === 0 && <p>No media uploaded yet.</p>}
          <ul>
            {media.map((item) => (
              <li key={item.media.id}>
                <strong>{item.media.filename}</strong> — {item.job.status}
                {isInFlight(item) && (
                  <progress value={item.job.progress} max={100}>
                    {item.job.progress}%
                  </progress>
                )}
                {item.job.status === "failed" && (
                  <>
                    <p role="alert">{item.job.error_message}</p>
                    <button
                      type="button"
                      onClick={() => handleRetry(item.job.id)}
                    >
                      Retry
                    </button>
                  </>
                )}
                {item.segments.length > 0 && (
                  <ol>
                    {item.segments.map((segment) => (
                      <li key={segment.index}>
                        <strong>{segment.speaker_label}</strong>{" "}
                        <span>
                          [{formatTimestamp(segment.start_ms)}–
                          {formatTimestamp(segment.end_ms)}, duration{" "}
                          {formatTimestamp(segment.duration_ms)}]
                        </span>
                        <p>{segment.text}</p>
                      </li>
                    ))}
                  </ol>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
