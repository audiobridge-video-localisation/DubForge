import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getProject,
  retryJob,
  updateSegment,
  uploadMedia,
  type MediaWithJob,
  type Project,
  type Segment,
  type SegmentUpdate,
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

interface SegmentDraft {
  text: string;
  translated_text: string;
  start_ms: number;
  end_ms: number;
}

function draftFrom(segment: Segment): SegmentDraft {
  return {
    text: segment.text,
    translated_text: segment.translated_text ?? "",
    start_ms: segment.start_ms,
    end_ms: segment.end_ms,
  };
}

function diffDraft(segment: Segment, draft: SegmentDraft): SegmentUpdate {
  const patch: SegmentUpdate = {};
  if (draft.text !== segment.text) patch.text = draft.text;
  if (draft.translated_text !== (segment.translated_text ?? "")) {
    patch.translated_text = draft.translated_text;
  }
  if (draft.start_ms !== segment.start_ms) patch.start_ms = draft.start_ms;
  if (draft.end_ms !== segment.end_ms) patch.end_ms = draft.end_ms;
  return patch;
}

function SegmentRow({
  segment,
  onSave,
}: {
  segment: Segment;
  onSave: (segmentId: string, patch: SegmentUpdate) => Promise<void>;
}) {
  const [draft, setDraft] = useState<SegmentDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isEditing = draft !== null;
  const isDirty =
    isEditing && Object.keys(diffDraft(segment, draft)).length > 0;
  const isInvalid =
    isEditing && (draft.start_ms < 0 || draft.start_ms >= draft.end_ms);

  function startEditing() {
    setDraft(draftFrom(segment));
    setSaveError(null);
  }

  function cancelEditing() {
    setDraft(null);
    setSaveError(null);
  }

  async function handleSave() {
    if (!draft || isInvalid) return;
    setSaving(true);
    setSaveError(null);
    try {
      await onSave(segment.id, diffDraft(segment, draft));
      setDraft(null);
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <li>
      <strong>{segment.speaker_label}</strong>{" "}
      <span>
        [{formatTimestamp(segment.start_ms)}–{formatTimestamp(segment.end_ms)},
        duration {formatTimestamp(segment.duration_ms)}]
      </span>{" "}
      {isDirty && <span role="status">Unsaved changes</span>}
      {!isEditing ? (
        <>
          <div style={{ display: "flex", gap: "1rem" }}>
            <p style={{ flex: 1 }}>{segment.text}</p>
            <p style={{ flex: 1 }}>{segment.translated_text}</p>
          </div>
          <button type="button" onClick={startEditing}>
            Edit
          </button>
        </>
      ) : (
        <>
          <div style={{ display: "flex", gap: "1rem" }}>
            <textarea
              style={{ flex: 1 }}
              value={draft.text}
              onChange={(event) =>
                setDraft({ ...draft, text: event.target.value })
              }
            />
            <textarea
              style={{ flex: 1 }}
              value={draft.translated_text}
              onChange={(event) =>
                setDraft({ ...draft, translated_text: event.target.value })
              }
            />
          </div>
          <label>
            Start (ms){" "}
            <input
              type="number"
              value={draft.start_ms}
              onChange={(event) =>
                setDraft({ ...draft, start_ms: Number(event.target.value) })
              }
            />
          </label>{" "}
          <label>
            End (ms){" "}
            <input
              type="number"
              value={draft.end_ms}
              onChange={(event) =>
                setDraft({ ...draft, end_ms: Number(event.target.value) })
              }
            />
          </label>
          {isInvalid && (
            <p role="alert">start must be 0 or greater and less than end</p>
          )}
          {saveError && <p role="alert">{saveError}</p>}
          <div>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || isInvalid}
            >
              {saving ? "Saving…" : "Save"}
            </button>{" "}
            <button type="button" onClick={cancelEditing} disabled={saving}>
              Cancel
            </button>
          </div>
        </>
      )}
    </li>
  );
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

  async function handleSegmentSave(
    mediaId: string,
    segmentId: string,
    patch: SegmentUpdate,
  ) {
    const updated = await updateSegment(segmentId, patch);
    setMedia((current) =>
      current.map((item) =>
        item.media.id === mediaId
          ? {
              ...item,
              segments: item.segments.map((s) =>
                s.id === segmentId ? updated : s,
              ),
            }
          : item,
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
                      <SegmentRow
                        key={segment.id}
                        segment={segment}
                        onSave={(segmentId, patch) =>
                          handleSegmentSave(item.media.id, segmentId, patch)
                        }
                      />
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
