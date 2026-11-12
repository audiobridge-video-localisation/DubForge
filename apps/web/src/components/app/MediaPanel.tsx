import { useRef, useState } from "react";

import {
  type ExportJob,
  type ExportKind,
  type MediaWithJob,
} from "../../api/client";
import {
  isAudioProblem,
  isJobInFlight,
  relativeTime,
  stageLabel,
  type Tone,
} from "../../lib/workflow";
import { summarizeError } from "../../lib/errors";
import { canRetryStalledJob, deriveWarnings } from "../../lib/warnings";
import { DubPlayer } from "./DubPlayer";
import { ExportCenter, type ExportsLoad } from "./ExportCenter";
import { SourcePlayer } from "./SourcePlayer";
import { SegmentTable, type SegmentHandlers } from "./SegmentTable";
import { StatusBadge } from "./StatusBadge";

const JOB_TONE: Record<string, Tone> = {
  pending: "info",
  processing: "info",
  completed: "ok",
  failed: "danger",
};

export interface MediaPanelProps extends SegmentHandlers {
  item: MediaWithJob;
  exportJobs: Partial<Record<ExportKind, ExportJob>>;
  exportsLoad: ExportsLoad;
  exportError: string | null;
  onReloadExports: () => void;
  dubbingError: string | null;
  batchRegenerating: boolean;
  batchRegenerateError: string | null;
  onRetry: (jobId: string) => Promise<void>;
  onReadyForDubbing: (mediaId: string) => void;
  onRegenerateProblems: (mediaId: string, segmentIds: string[]) => void;
  onExport: (
    mediaId: string,
    kind: ExportKind,
    acceptLongLines?: boolean,
  ) => void;
}

function Meter({
  value,
  max,
  label,
}: {
  value: number;
  max: number;
  label: string;
}) {
  const percent = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="meter">
      <div className="meter-top">
        <span>{label}</span>
        <b>
          {value} / {max}
        </b>
      </div>
      <div
        className="progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-label={label}
      >
        <i style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export function MediaPanel({
  item,
  exportJobs,
  exportsLoad,
  exportError,
  onReloadExports,
  dubbingError,
  batchRegenerating,
  batchRegenerateError,
  onRetry,
  onReadyForDubbing,
  onRegenerateProblems,
  onExport,
  ...segmentHandlers
}: MediaPanelProps) {
  const {
    media,
    job,
    segments,
    approved_count,
    total_count,
    usable_audio_count,
  } = item;
  const mediaRef = useRef<HTMLMediaElement | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const sourceRef = useRef<HTMLVideoElement | null>(null);

  // selecting a line seeks the original video, so the reviewer sees what was said
  function seekTo(ms: number) {
    const el = sourceRef.current;
    if (!el) return;
    el.currentTime = ms / 1000;
    void el.play().catch(() => undefined);
  }
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const processing = isJobInFlight(job);
  const warnings = deriveWarnings(item);
  const failure = summarizeError(job.error_message);
  const problemIds = segments
    .filter((s) => isAudioProblem(s.audio_status))
    .map((s) => s.id);
  const needAudioIds = segments
    .filter((s) => s.audio_status === "no_audio")
    .map((s) => s.id);
  const allApproved = total_count > 0 && approved_count === total_count;
  const dubReady = allApproved && usable_audio_count === total_count;
  async function retry() {
    setRetrying(true);
    setRetryError(null);
    try {
      await onRetry(job.id);
    } catch (err) {
      setRetryError((err as Error).message);
    } finally {
      setRetrying(false);
    }
  }

  return (
    <article className="card media">
      <header className="media-head">
        <div>
          <h2 title={media.filename}>{media.filename}</h2>
          <p>Uploaded {relativeTime(new Date(media.created_at))}</p>
        </div>
        <StatusBadge
          tone={JOB_TONE[job.status] ?? "neutral"}
          pulse={processing}
        >
          {job.status === "completed"
            ? "Processed"
            : job.status === "failed"
              ? "Failed"
              : job.status === "pending"
                ? "Queued"
                : "Processing"}
        </StatusBadge>
      </header>

      {processing && (
        <div className="job" role="status" aria-live="polite">
          <div className="job-top">
            <strong>{stageLabel(job)}</strong>
            <span>{job.status === "pending" ? "—" : `${job.progress}%`}</span>
          </div>
          <div
            className="progress progress-live"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={job.progress}
            aria-label="Processing progress"
          >
            <i style={{ width: `${Math.max(job.progress, 4)}%` }} />
          </div>
          <p>This page updates on its own. You can leave and come back.</p>
          {canRetryStalledJob(job) && (
            <div className="job-stalled">
              <p>
                Nothing has changed for several minutes, so this job may have
                been interrupted. You can run it again.
              </p>
              <button
                type="button"
                className="btn btn-sm btn-primary"
                disabled={retrying}
                onClick={retry}
              >
                {retrying ? "Retrying…" : "Retry"}
              </button>
              {retryError && (
                <p className="inline-error" role="alert">
                  {retryError}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {job.status === "failed" && (
        <div className="notice notice-danger" role="alert">
          <div>
            <strong>Processing failed</strong>
            <p>{failure.headline}</p>
            {failure.details && (
              <details className="tech">
                <summary>Show technical details</summary>
                <pre>{failure.details}</pre>
              </details>
            )}
            {retryError && <p>{retryError}</p>}
          </div>
          <button
            type="button"
            className="btn btn-primary"
            disabled={retrying}
            onClick={retry}
          >
            {retrying ? "Retrying…" : "Retry"}
          </button>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="notice notice-warn" role="status">
          <div>
            <strong>
              {warnings.length === 1
                ? "Heads up"
                : `${warnings.length} things to check`}
            </strong>
            <ul className="warn-list">
              {warnings.map((w) => (
                <li key={w.id}>
                  <b>{w.title}.</b> {w.detail}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {job.status === "completed" && total_count === 0 && (
        <div className="notice notice-warn" role="status">
          <div>
            <strong>No lines were found</strong>
            <p>
              Processing finished, but no speech was detected in this video.
            </p>
          </div>
        </div>
      )}

      {total_count > 0 && (
        <>
          <div className="stats">
            <Meter
              value={approved_count}
              max={total_count}
              label="Lines approved"
            />
            <Meter
              value={usable_audio_count}
              max={total_count}
              label="Dubbed audio ready"
            />
            <div className="stats-actions">
              {needAudioIds.length > 0 && (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={batchRegenerating}
                  onClick={() => onRegenerateProblems(media.id, needAudioIds)}
                >
                  {batchRegenerating
                    ? "Generating…"
                    : `Generate dubbed audio (${needAudioIds.length})`}
                </button>
              )}
              {problemIds.length > 0 && (
                <button
                  type="button"
                  className="btn"
                  disabled={batchRegenerating}
                  onClick={() => onRegenerateProblems(media.id, problemIds)}
                >
                  {batchRegenerating
                    ? "Regenerating…"
                    : `Regenerate problem audio (${problemIds.length})`}
                </button>
              )}
              <button
                type="button"
                className="btn"
                disabled={media.ready_for_dubbing || !dubReady}
                onClick={() => onReadyForDubbing(media.id)}
              >
                {media.ready_for_dubbing
                  ? "Marked ready for dubbing"
                  : "Mark ready for dubbing"}
              </button>
            </div>
          </div>
          {batchRegenerateError && (
            <p className="inline-error" role="alert">
              {batchRegenerateError}
            </p>
          )}
          {dubbingError && (
            <p className="inline-error" role="alert">
              {dubbingError}
            </p>
          )}

          <ExportCenter
            item={item}
            exportJobs={exportJobs}
            exportsLoad={exportsLoad}
            exportError={exportError}
            onReloadExports={onReloadExports}
            onExport={onExport}
          />

          <SourcePlayer
            mediaId={media.id}
            segments={segments}
            videoRef={sourceRef}
            onActive={setActiveId}
          />

          <DubPlayer
            jobs={exportJobs}
            segments={segments}
            mediaRef={mediaRef}
            activeId={activeId}
            onActive={setActiveId}
          />

          <SegmentTable
            segments={segments}
            activeId={activeId}
            onSeek={seekTo}
            {...segmentHandlers}
          />
        </>
      )}
    </article>
  );
}
