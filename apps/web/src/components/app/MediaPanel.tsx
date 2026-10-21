import { useState } from "react";

import {
  exportDownloadUrl,
  srtDownloadUrl,
  vttDownloadUrl,
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
import { SegmentTable, type SegmentHandlers } from "./SegmentTable";
import { StatusBadge } from "./StatusBadge";

const EXPORT_KINDS: ExportKind[] = ["mp3", "mp4"];
const EXPORT_LABEL: Record<ExportKind, string> = {
  mp3: "Dubbed audio (MP3)",
  mp4: "Dubbed video (MP4)",
};

const JOB_TONE: Record<string, Tone> = {
  pending: "info",
  processing: "info",
  completed: "ok",
  failed: "danger",
};

function inFlight(job: ExportJob | undefined): boolean {
  return job?.status === "pending" || job?.status === "processing";
}

export interface MediaPanelProps extends SegmentHandlers {
  item: MediaWithJob;
  exportJobs: Partial<Record<ExportKind, ExportJob>>;
  exportError: string | null;
  dubbingError: string | null;
  batchRegenerating: boolean;
  batchRegenerateError: string | null;
  onRetry: (jobId: string) => Promise<void>;
  onReadyForDubbing: (mediaId: string) => void;
  onRegenerateProblems: (mediaId: string, segmentIds: string[]) => void;
  onExport: (mediaId: string, kind: ExportKind) => void;
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
  exportError,
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
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const processing = isJobInFlight(job);
  const problemIds = segments
    .filter((s) => isAudioProblem(s.audio_status))
    .map((s) => s.id);
  const allApproved = total_count > 0 && approved_count === total_count;
  const dubReady = allApproved && usable_audio_count === total_count;
  const voices = Array.from(
    new Set(
      segments
        .map((s) => s.artifact?.voice_profile)
        .filter((v): v is string => Boolean(v)),
    ),
  );

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
        </div>
      )}

      {job.status === "failed" && (
        <div className="notice notice-danger" role="alert">
          <div>
            <strong>Processing failed</strong>
            <p>{job.error_message ?? "The job stopped before it finished."}</p>
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
                disabled={media.ready_for_dubbing || !allApproved}
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

          <section className="deliver" aria-label="Export">
            <div className="deliver-col">
              <h3>Subtitles</h3>
              <p>Available as soon as there are lines.</p>
              <div className="deliver-row">
                <a className="btn btn-sm" href={srtDownloadUrl(media.id)}>
                  Download SRT
                </a>
                <a className="btn btn-sm" href={vttDownloadUrl(media.id)}>
                  Download VTT
                </a>
              </div>
            </div>
            <div className="deliver-col">
              <h3>Dubbed output</h3>
              <p>
                {dubReady
                  ? voices.length > 0
                    ? `Voices used: ${voices.join(", ")}`
                    : "Every line is approved with usable audio."
                  : "Unlocks when every line is approved and has usable audio."}
              </p>
              <div className="deliver-row">
                {EXPORT_KINDS.map((kind) => (
                  <button
                    key={kind}
                    type="button"
                    className="btn btn-sm btn-primary"
                    disabled={!dubReady || inFlight(exportJobs[kind])}
                    onClick={() => onExport(media.id, kind)}
                  >
                    Export {kind.toUpperCase()}
                  </button>
                ))}
              </div>
              {EXPORT_KINDS.map((kind) => {
                const exportJob = exportJobs[kind];
                if (!exportJob) return null;
                return (
                  <div className="export-job" key={kind}>
                    <span>{EXPORT_LABEL[kind]}</span>
                    <StatusBadge
                      tone={JOB_TONE[exportJob.status] ?? "neutral"}
                      pulse={inFlight(exportJob)}
                    >
                      {exportJob.status}
                    </StatusBadge>
                    {inFlight(exportJob) && (
                      <div
                        className="progress progress-live"
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={exportJob.progress}
                        aria-label={`${kind.toUpperCase()} export progress`}
                      >
                        <i
                          style={{
                            width: `${Math.max(exportJob.progress, 4)}%`,
                          }}
                        />
                      </div>
                    )}
                    {exportJob.status === "completed" && (
                      <a
                        className="link"
                        href={exportDownloadUrl(exportJob.id)}
                      >
                        Download
                      </a>
                    )}
                    {exportJob.status === "failed" && (
                      <span className="inline-error" role="alert">
                        {exportJob.error_message}
                      </span>
                    )}
                  </div>
                );
              })}
              {exportError && (
                <p className="inline-error" role="alert">
                  {exportError}
                </p>
              )}
            </div>
          </section>

          <SegmentTable segments={segments} {...segmentHandlers} />
        </>
      )}
    </article>
  );
}
