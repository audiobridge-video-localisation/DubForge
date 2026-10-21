import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  approveSegment,
  exportMp3,
  exportMp4,
  getExportJob,
  getProject,
  markReadyForDubbing,
  regenerateSegment,
  requestSegmentChanges,
  retryJob,
  updateSegment,
  uploadMedia,
  type Artifact,
  type ExportJob,
  type ExportKind,
  type MediaWithJob,
  type Project,
  type Segment,
  type SegmentUpdate,
  type UploadOptions,
} from "../api/client";
import { AppShell } from "../components/app/AppShell";
import { MediaPanel } from "../components/app/MediaPanel";
import { ProjectHeader } from "../components/app/ProjectHeader";
import { UploadDropzone } from "../components/app/UploadDropzone";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { isArtifactInFlight, isJobInFlight } from "../lib/workflow";

const EXPORT_KINDS: ExportKind[] = ["mp3", "mp4"];
const POLL_INTERVAL_MS = 3000;

function isExportInFlight(job: ExportJob | undefined): boolean {
  return job?.status === "pending" || job?.status === "processing";
}

export function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [media, setMedia] = useState<MediaWithJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const [dubbingError, setDubbingError] = useState<
    Record<string, string | null>
  >({});

  const [batchRegenerating, setBatchRegenerating] = useState<
    Record<string, boolean>
  >({});
  const [batchRegenerateError, setBatchRegenerateError] = useState<
    Record<string, string | null>
  >({});

  const [exportJobs, setExportJobs] = useState<
    Record<string, Partial<Record<ExportKind, ExportJob>>>
  >({});
  const [exportError, setExportError] = useState<Record<string, string | null>>(
    {},
  );

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getProject(id)
      .then((detail) => {
        if (cancelled) return;
        setProject(detail);
        setMedia(detail.media);
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
  }, [id, attempt]);

  useEffect(() => {
    const anyInFlight = media.some(
      (item) =>
        isJobInFlight(item.job) ||
        item.segments.some((s) => isArtifactInFlight(s.artifact)),
    );
    if (!id || !anyInFlight) return;

    const interval = setInterval(() => {
      getProject(id)
        .then((detail) => {
          setMedia(detail.media);
          setOffline(false);
        })
        .catch(() => setOffline(true));
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [id, media]);

  useEffect(() => {
    const inFlightJobs = Object.entries(exportJobs).flatMap(
      ([mediaId, byKind]) =>
        EXPORT_KINDS.filter((kind) => isExportInFlight(byKind[kind])).map(
          (kind) => ({
            mediaId,
            kind,
            job: byKind[kind] as ExportJob,
          }),
        ),
    );
    if (inFlightJobs.length === 0) return;

    const interval = setInterval(() => {
      inFlightJobs.forEach(({ mediaId, kind, job }) => {
        getExportJob(job.id)
          .then((updated) => {
            setExportJobs((current) => ({
              ...current,
              [mediaId]: { ...current[mediaId], [kind]: updated },
            }));
          })
          .catch(() => setOffline(true));
      });
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [exportJobs]);

  async function handleUpload(file: File, options: UploadOptions) {
    if (!id) return;
    const result = await uploadMedia(id, file, options);
    setMedia((current) => [result, ...current]);
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
          usable_audio_count: segments.filter((s) => s.audio_status === "ready")
            .length,
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

  function applySegmentArtifact(
    mediaId: string,
    segmentId: string,
    artifact: Artifact,
  ) {
    // regenerateSegment always resets the artifact to "pending", so the
    // segment's derived audio_status is known immediately without waiting
    // for the next poll to refetch the full, server-computed value.
    setMedia((current) =>
      current.map((item) => {
        if (item.media.id !== mediaId) return item;
        const segments = item.segments.map((s) =>
          s.id === segmentId
            ? { ...s, artifact, audio_status: "pending" as const }
            : s,
        );
        return {
          ...item,
          segments,
          usable_audio_count: segments.filter((s) => s.audio_status === "ready")
            .length,
        };
      }),
    );
  }

  async function handleSegmentRegenerate(mediaId: string, segmentId: string) {
    const artifact = await regenerateSegment(segmentId);
    applySegmentArtifact(mediaId, segmentId, artifact);
  }

  async function handleRegenerateProblemAudio(
    mediaId: string,
    segmentIds: string[],
  ) {
    setBatchRegenerateError((current) => ({ ...current, [mediaId]: null }));
    setBatchRegenerating((current) => ({ ...current, [mediaId]: true }));
    try {
      const results = await Promise.allSettled(
        segmentIds.map((segmentId) => regenerateSegment(segmentId)),
      );
      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          applySegmentArtifact(mediaId, segmentIds[index], result.value);
        }
      });
      const failures = results.filter((r) => r.status === "rejected");
      if (failures.length > 0) {
        setBatchRegenerateError((current) => ({
          ...current,
          [mediaId]: `${failures.length} of ${segmentIds.length} segments failed to queue for regeneration`,
        }));
      }
    } finally {
      setBatchRegenerating((current) => ({ ...current, [mediaId]: false }));
    }
  }

  async function handleExport(mediaId: string, kind: ExportKind) {
    setExportError((current) => ({ ...current, [mediaId]: null }));
    try {
      const job =
        kind === "mp3" ? await exportMp3(mediaId) : await exportMp4(mediaId);
      setExportJobs((current) => ({
        ...current,
        [mediaId]: { ...current[mediaId], [kind]: job },
      }));
    } catch (err) {
      setExportError((current) => ({
        ...current,
        [mediaId]: (err as Error).message,
      }));
    }
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

  useDocumentTitle(
    project ? `${project.name} · DubForge` : "Project · DubForge",
  );

  if (loading) {
    return (
      <AppShell>
        <div
          className="skeleton skeleton-header"
          aria-busy="true"
          aria-label="Loading project"
        />
        <div className="skeleton skeleton-card" />
      </AppShell>
    );
  }

  if (error || !project) {
    return (
      <AppShell>
        <section className="card empty" role="alert">
          <h1>We couldn&apos;t open this project</h1>
          <p>{error ?? "The project could not be found."}</p>
          <div className="empty-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setAttempt((n) => n + 1)}
            >
              Try again
            </button>
            <Link className="btn" to="/app">
              Back to projects
            </Link>
          </div>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <ProjectHeader project={project} media={media} />
      {offline && (
        <p className="banner banner-warn" role="status">
          Lost contact with the API. Showing the last data we had, and retrying.
        </p>
      )}

      <UploadDropzone onUpload={handleUpload} />

      <section className="media-list" aria-label="Uploaded videos">
        {media.length === 0 ? (
          <div className="card empty">
            <h2>No videos yet</h2>
            <p>
              Upload a video above and its transcript and translation will
              appear here.
            </p>
          </div>
        ) : (
          media.map((item) => (
            <MediaPanel
              key={item.media.id}
              item={item}
              exportJobs={exportJobs[item.media.id] ?? {}}
              exportError={exportError[item.media.id] ?? null}
              dubbingError={dubbingError[item.media.id] ?? null}
              batchRegenerating={batchRegenerating[item.media.id] ?? false}
              batchRegenerateError={batchRegenerateError[item.media.id] ?? null}
              onRetry={handleRetry}
              onReadyForDubbing={handleReadyForDubbing}
              onRegenerateProblems={handleRegenerateProblemAudio}
              onExport={handleExport}
              onSave={(segmentId, patch) =>
                handleSegmentSave(item.media.id, segmentId, patch)
              }
              onApprove={(segmentId) =>
                handleSegmentApprove(item.media.id, segmentId)
              }
              onRequestChanges={(segmentId) =>
                handleSegmentRequestChanges(item.media.id, segmentId)
              }
              onRegenerate={(segmentId) =>
                handleSegmentRegenerate(item.media.id, segmentId)
              }
            />
          ))
        )}
      </section>
    </AppShell>
  );
}
