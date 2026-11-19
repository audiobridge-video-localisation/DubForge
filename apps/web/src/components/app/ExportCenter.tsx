import {
  exportDownloadUrl,
  srtDownloadUrl,
  vttDownloadUrl,
  type ExportJob,
  type ExportKind,
  type MediaWithJob,
} from "../../api/client";
import {
  blockerTitle,
  deriveExportCenter,
  describeLines,
  isExportStale,
} from "../../lib/exportCenter";
import { summarizeError } from "../../lib/errors";
import { formatDuration, type Tone } from "../../lib/workflow";
import { StatusBadge } from "./StatusBadge";

export type ExportsLoad = "loading" | "ready" | "error";

const EXPORT_KINDS: ExportKind[] = ["mp3", "mp4"];
const EXPORT_LABEL: Record<ExportKind, string> = {
  mp3: "Dubbed audio (MP3)",
  mp4: "Dubbed video (MP4)",
};
const JOB_LABEL: Record<string, string> = {
  pending: "Queued",
  processing: "Exporting",
  completed: "Ready",
  failed: "Failed",
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

export interface ExportCenterProps {
  item: MediaWithJob;
  exportJobs: Partial<Record<ExportKind, ExportJob>>;
  /** whether the saved export state has been fetched from the API yet */
  exportsLoad: ExportsLoad;
  exportError: string | null;
  onReloadExports: () => void;
  onExport: (
    mediaId: string,
    kind: ExportKind,
    acceptLongLines?: boolean,
  ) => void;
}

function Check({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <li className={ok ? "xc-check xc-ok" : "xc-check xc-no"}>
      <span aria-hidden="true">{ok ? "✓" : "•"}</span>
      <span>{children}</span>
      <span className="sr-only">{ok ? "done" : "not done"}</span>
    </li>
  );
}

export function ExportCenter({
  item,
  exportJobs,
  exportsLoad,
  exportError,
  onReloadExports,
  onExport,
}: ExportCenterProps) {
  const { media } = item;
  const state = deriveExportCenter(item);
  const { summary } = state;
  const allApproved = state.total > 0 && state.approved === state.total;
  const allAudio = state.total > 0 && state.audioReady === state.total;
  // long dubs alone never stop an export: the video pauses on a frame for them
  const exportable = state.ready || state.canExportAnyway;
  const pausing = !state.ready && state.canExportAnyway;

  return (
    <section className="export-center" aria-label="Export center">
      <header className="xc-head">
        <div>
          <h3>Export center</h3>
          <p>
            {state.ready
              ? "Everything is approved and has usable audio."
              : pausing
                ? "Ready. The video pauses briefly under the long lines below."
                : "Finish the items below to unlock the dubbed export."}
          </p>
        </div>
        <StatusBadge tone={state.ready ? "ok" : pausing ? "info" : "warn"}>
          {exportable ? "Ready to export" : "Not ready yet"}
        </StatusBadge>
      </header>

      <div className="xc-grid">
        <div className="xc-col">
          <h4>Readiness</h4>
          <ul className="xc-checks">
            <Check ok={allApproved}>
              <b>
                {state.approved} of {state.total}
              </b>{" "}
              lines approved
            </Check>
            <Check ok={allAudio}>
              <b>
                {state.audioReady} of {state.total}
              </b>{" "}
              lines have usable dubbed audio
            </Check>
          </ul>

          {state.blockers.length > 0 ? (
            <div
              className={pausing ? "xc-blockers xc-pausing" : "xc-blockers"}
              role="status"
            >
              <strong>
                {pausing
                  ? "Nothing is blocking export"
                  : state.blockers.length === 1
                    ? "1 thing is blocking export"
                    : `${state.blockers.length} things are blocking export`}
              </strong>
              <ul>
                {state.blockers.map((blocker) => (
                  <li key={blocker.kind} data-blocker={blocker.kind}>
                    <b>{blockerTitle(blocker)}.</b>{" "}
                    <span className="xc-lines">
                      {describeLines(blocker.lines)}.
                    </span>{" "}
                    {blocker.fix}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="xc-clear" role="status">
              Nothing is blocking export.
            </p>
          )}
        </div>

        <div className="xc-col">
          <h4>Project summary</h4>
          <dl className="xc-summary">
            <div>
              <dt>File</dt>
              <dd title={media.filename}>{media.filename}</dd>
            </div>
            <div>
              <dt>Lines</dt>
              <dd>{summary.lineCount}</dd>
            </div>
            <div>
              <dt>Speakers</dt>
              <dd>{summary.speakerCount}</dd>
            </div>
            <div>
              <dt>Length</dt>
              <dd>{formatDuration(summary.durationMs)}</dd>
            </div>
            <div>
              <dt>Dubbed into</dt>
              <dd>{summary.language ?? "Not known yet"}</dd>
            </div>
            <div>
              <dt>Voice</dt>
              <dd>
                {summary.voices.length > 0
                  ? summary.voices.join(", ")
                  : "None generated yet"}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="deliver">
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
            {exportable
              ? "Choose a format. Each export runs in the background."
              : "Locked until nothing is blocking export."}
          </p>
          <div className="deliver-row">
            {EXPORT_KINDS.map((kind) => {
              const job = exportJobs[kind];
              const retrying = job?.status === "failed";
              return (
                <button
                  key={kind}
                  type="button"
                  className="btn btn-sm btn-primary"
                  disabled={!exportable || inFlight(job)}
                  onClick={() => onExport(media.id, kind, pausing)}
                >
                  {retrying
                    ? `Retry ${kind.toUpperCase()} export`
                    : `Export ${kind.toUpperCase()}`}
                </button>
              );
            })}
          </div>

          {exportsLoad === "loading" && (
            <p className="xc-note" role="status" aria-busy="true">
              Checking for earlier exports…
            </p>
          )}
          {exportsLoad === "error" && (
            <p className="inline-error xc-reload" role="alert">
              Couldn&apos;t load earlier exports.{" "}
              <button
                type="button"
                className="btn btn-sm"
                onClick={onReloadExports}
              >
                Try again
              </button>
            </p>
          )}
          {exportsLoad === "ready" &&
            EXPORT_KINDS.every((kind) => !exportJobs[kind]) && (
              <p className="xc-note">Nothing has been exported yet.</p>
            )}

          {EXPORT_KINDS.map((kind) => {
            const job = exportJobs[kind];
            if (!job) return null;
            const stale = isExportStale(job, item);
            return (
              <div className="export-job" key={kind}>
                <span>{EXPORT_LABEL[kind]}</span>
                <StatusBadge
                  tone={JOB_TONE[job.status] ?? "neutral"}
                  pulse={inFlight(job)}
                >
                  {JOB_LABEL[job.status] ?? job.status}
                </StatusBadge>
                {inFlight(job) && (
                  <div
                    className="progress progress-live"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={job.progress}
                    aria-label={`${kind.toUpperCase()} export progress`}
                  >
                    <i style={{ width: `${Math.max(job.progress, 4)}%` }} />
                  </div>
                )}
                {job.status === "completed" && (
                  <a className="link" href={exportDownloadUrl(job.id)}>
                    Download
                  </a>
                )}
                {job.status === "failed" && (
                  <span className="inline-error" role="alert">
                    {summarizeError(job.error_message).headline}
                  </span>
                )}
                {stale && (
                  <span className="xc-stale" role="status">
                    Audio changed after this export. Export again to include the
                    changes.
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
      </div>
    </section>
  );
}
