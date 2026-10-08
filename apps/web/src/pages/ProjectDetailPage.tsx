import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  approveSegment,
  getProject,
  markReadyForDubbing,
  regenerateSegment,
  requestSegmentChanges,
  retryJob,
  updateSegment,
  uploadMedia,
  type Artifact,
  type MediaWithJob,
  type Project,
  type Segment,
  type SegmentUpdate,
} from "../api/client";

const REVIEW_STATUS_LABELS = {
  pending: "Pending",
  approved: "Approved",
  needs_changes: "Needs changes",
};

const ARTIFACT_STATUS_LABELS = {
  pending: "Pending",
  processing: "Processing",
  completed: "Completed",
  failed: "Failed",
  outdated: "Outdated",
};

function isArtifactInFlight(artifact: Artifact | null): boolean {
  return artifact?.status === "pending" || artifact?.status === "processing";
}

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
  speaker_label: string;
  start_ms: number;
  end_ms: number;
}

function draftFrom(segment: Segment): SegmentDraft {
  return {
    text: segment.text,
    translated_text: segment.translated_text ?? "",
    speaker_label: segment.speaker_label,
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
  if (draft.speaker_label !== segment.speaker_label) {
    patch.speaker_label = draft.speaker_label;
  }
  if (draft.start_ms !== segment.start_ms) patch.start_ms = draft.start_ms;
  if (draft.end_ms !== segment.end_ms) patch.end_ms = draft.end_ms;
  return patch;
}

function SegmentRow({
  segment,
  onSave,
  onApprove,
  onRequestChanges,
  onRegenerate,
}: {
  segment: Segment;
  onSave: (segmentId: string, patch: SegmentUpdate) => Promise<void>;
  onApprove: (segmentId: string) => Promise<void>;
  onRequestChanges: (segmentId: string) => Promise<void>;
  onRegenerate: (segmentId: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<SegmentDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [reviewActionError, setReviewActionError] = useState<string | null>(
    null,
  );
  const [regenerateError, setRegenerateError] = useState<string | null>(null);

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

  async function handleApprove() {
    setReviewActionError(null);
    try {
      await onApprove(segment.id);
    } catch (err) {
      setReviewActionError((err as Error).message);
    }
  }

  async function handleRequestChanges() {
    setReviewActionError(null);
    try {
      await onRequestChanges(segment.id);
    } catch (err) {
      setReviewActionError((err as Error).message);
    }
  }

  async function handleRegenerate() {
    setRegenerateError(null);
    try {
      await onRegenerate(segment.id);
    } catch (err) {
      setRegenerateError((err as Error).message);
    }
  }

  return (
    <li>
      <span>{REVIEW_STATUS_LABELS[segment.review_status]}</span>{" "}
      <span>
        [{formatTimestamp(segment.start_ms)}–{formatTimestamp(segment.end_ms)},
        duration {formatTimestamp(segment.duration_ms)}]
      </span>{" "}
      {isDirty && <span role="status">Unsaved changes</span>}
      {reviewActionError && <p role="alert">{reviewActionError}</p>}
      {!isEditing ? (
        <>
          <p>
            <strong>{segment.speaker_label}</strong>
          </p>
          <div style={{ display: "flex", gap: "1rem" }}>
            <p style={{ flex: 1 }}>{segment.text}</p>
            <p style={{ flex: 1 }}>{segment.translated_text}</p>
          </div>
          <button type="button" onClick={startEditing}>
            Edit
          </button>{" "}
          <button type="button" onClick={handleApprove}>
            Approve
          </button>{" "}
          <button type="button" onClick={handleRequestChanges}>
            Request changes
          </button>{" "}
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={isArtifactInFlight(segment.artifact)}
          >
            Regenerate
          </button>
          <p>
            Artifact:{" "}
            {segment.artifact
              ? ARTIFACT_STATUS_LABELS[segment.artifact.status]
              : "None yet"}
            {segment.artifact?.audio_path &&
              ` (${segment.artifact.audio_path})`}
            {segment.artifact?.duration_ms != null &&
              `, ${segment.artifact.duration_ms}ms`}
          </p>
          {segment.artifact?.status === "failed" &&
            segment.artifact.error_message && (
              <p role="alert">{segment.artifact.error_message}</p>
            )}
          {regenerateError && <p role="alert">{regenerateError}</p>}
        </>
      ) : (
        <>
          <label>
            Speaker{" "}
            <input
              value={draft.speaker_label}
              onChange={(event) =>
                setDraft({ ...draft, speaker_label: event.target.value })
              }
            />
          </label>
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

  const [dubbingError, setDubbingError] = useState<
    Record<string, string | null>
  >({});

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
    const anyInFlight = media.some(
      (item) =>
        isInFlight(item) ||
        item.segments.some((s) => isArtifactInFlight(s.artifact)),
    );
    if (!id || !anyInFlight) return;

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

  function applySegmentUpdate(
    mediaId: string,
    segmentId: string,
    updated: Segment,
  ) {
    setMedia((current) =>
      current.map((item) => {
        if (item.media.id !== mediaId) return item;
        const segments = item.segments.map((s) =>
          s.id === segmentId ? updated : s,
        );
        return {
          ...item,
          segments,
          approved_count: segments.filter((s) => s.review_status === "approved")
            .length,
          total_count: segments.length,
        };
      }),
    );
  }

  async function handleSegmentSave(
    mediaId: string,
    segmentId: string,
    patch: SegmentUpdate,
  ) {
    const updated = await updateSegment(segmentId, patch);
    applySegmentUpdate(mediaId, segmentId, updated);
  }

  async function handleSegmentApprove(mediaId: string, segmentId: string) {
    const updated = await approveSegment(segmentId);
    applySegmentUpdate(mediaId, segmentId, updated);
  }

  async function handleSegmentRequestChanges(
    mediaId: string,
    segmentId: string,
  ) {
    const updated = await requestSegmentChanges(segmentId);
    applySegmentUpdate(mediaId, segmentId, updated);
  }

  async function handleSegmentRegenerate(mediaId: string, segmentId: string) {
    const artifact = await regenerateSegment(segmentId);
    setMedia((current) =>
      current.map((item) => {
        if (item.media.id !== mediaId) return item;
        return {
          ...item,
          segments: item.segments.map((s) =>
            s.id === segmentId ? { ...s, artifact } : s,
          ),
        };
      }),
    );
  }

  async function handleReadyForDubbing(mediaId: string) {
    setDubbingError((current) => ({ ...current, [mediaId]: null }));
    try {
      const updatedMedia = await markReadyForDubbing(mediaId);
      setMedia((current) =>
        current.map((item) =>
          item.media.id === mediaId ? { ...item, media: updatedMedia } : item,
        ),
      );
    } catch (err) {
      setDubbingError((current) => ({
        ...current,
        [mediaId]: (err as Error).message,
      }));
    }
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
                  <>
                    <p>
                      {item.approved_count} / {item.total_count} segments
                      approved
                    </p>
                    <button
                      type="button"
                      disabled={
                        item.media.ready_for_dubbing ||
                        item.total_count === 0 ||
                        item.approved_count !== item.total_count
                      }
                      onClick={() => handleReadyForDubbing(item.media.id)}
                    >
                      {item.media.ready_for_dubbing
                        ? "Ready for dubbing"
                        : "Mark ready for dubbing"}
                    </button>
                    {dubbingError[item.media.id] && (
                      <p role="alert">{dubbingError[item.media.id]}</p>
                    )}
                    <ol>
                      {item.segments.map((segment) => (
                        <SegmentRow
                          key={segment.id}
                          segment={segment}
                          onSave={(segmentId, patch) =>
                            handleSegmentSave(item.media.id, segmentId, patch)
                          }
                          onApprove={(segmentId) =>
                            handleSegmentApprove(item.media.id, segmentId)
                          }
                          onRequestChanges={(segmentId) =>
                            handleSegmentRequestChanges(
                              item.media.id,
                              segmentId,
                            )
                          }
                          onRegenerate={(segmentId) =>
                            handleSegmentRegenerate(item.media.id, segmentId)
                          }
                        />
                      ))}
                    </ol>
                  </>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
