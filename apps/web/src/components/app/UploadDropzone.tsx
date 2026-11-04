import { useEffect, useId, useRef, useState } from "react";

import type { UploadOptions } from "../../api/client";
import {
  MAX_UPLOAD_BYTES,
  describeSelection,
  uploadAdvice,
  validateVideoFile,
} from "../../lib/uploadRules";
import { formatBytes } from "../../lib/workflow";

type Phase =
  | { kind: "idle" }
  | { kind: "ready"; file: File; note: string | null }
  | { kind: "uploading"; file: File; percent: number }
  | { kind: "success"; file: File }
  | { kind: "error"; file: File | null; message: string };

export function UploadDropzone({
  onUpload,
}: {
  onUpload: (file: File, options: UploadOptions) => Promise<void>;
}) {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController | null>(null);
  const hintId = useId();
  const depth = useRef(0);

  useEffect(() => () => abort.current?.abort(), []);

  function choose(files: ArrayLike<File> | null | undefined) {
    const file = files?.[0];
    if (!file) {
      // e.g. text or a link was dragged in instead of a file
      setPhase({
        kind: "error",
        file: null,
        message:
          "That wasn't a file. Drag a video file here, or browse for one.",
      });
      return;
    }
    const problem = validateVideoFile(file);
    if (problem) {
      setPhase({ kind: "error", file: null, message: problem });
      return;
    }
    const note = [describeSelection(files.length), uploadAdvice(file)]
      .filter(Boolean)
      .join(" ");
    setPhase({ kind: "ready", file, note: note || null });
  }

  async function start(file: File) {
    const controller = new AbortController();
    abort.current = controller;
    setPhase({ kind: "uploading", file, percent: 0 });
    try {
      await onUpload(file, {
        signal: controller.signal,
        onProgress: (percent) =>
          setPhase((now) =>
            now.kind === "uploading" ? { ...now, percent } : now,
          ),
      });
      setPhase({ kind: "success", file });
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setPhase({ kind: "ready", file, note: null });
      } else {
        setPhase({ kind: "error", file, message: (err as Error).message });
      }
    } finally {
      abort.current = null;
      if (input.current) input.current.value = "";
    }
  }

  function reset() {
    setPhase({ kind: "idle" });
    if (input.current) input.current.value = "";
  }

  const busy = phase.kind === "uploading";

  return (
    <section className="card upload" aria-labelledby={`${hintId}-title`}>
      <div className="upload-head">
        <h2 id={`${hintId}-title`}>Upload a video</h2>
        <p>Processing starts automatically once the upload finishes.</p>
      </div>

      <div
        className={`dropzone dz-${phase.kind}${dragging ? " dz-over" : ""}`}
        onDragEnter={(event) => {
          event.preventDefault();
          depth.current += 1;
          if (!busy) setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => {
          depth.current = Math.max(0, depth.current - 1);
          if (depth.current === 0) setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          depth.current = 0;
          setDragging(false);
          if (!busy) choose(event.dataTransfer.files);
        }}
      >
        <input
          ref={input}
          id={`${hintId}-file`}
          className="sr-only"
          type="file"
          accept="video/*,.mkv,.mov,.m4v"
          aria-describedby={hintId}
          disabled={busy}
          onChange={(event) => choose(event.target.files)}
        />

        {(phase.kind === "idle" || phase.kind === "error") && (
          <label htmlFor={`${hintId}-file`} className="dz-body">
            <span className="dz-icon" aria-hidden="true">
              ↑
            </span>
            <span className="dz-title">
              {dragging ? (
                "Drop to select this video"
              ) : (
                <>
                  Drag a video here, or <u>browse your files</u>
                </>
              )}
            </span>
            <span id={hintId} className="dz-hint">
              MP4, MOV, MKV, WebM and most other video formats · up to{" "}
              {formatBytes(MAX_UPLOAD_BYTES)} · spoken audio should be English
            </span>
          </label>
        )}

        {phase.kind === "ready" && (
          <div className="dz-file">
            <FileChip file={phase.file} />
            {phase.note && (
              <p className="dz-note" role="status">
                {phase.note}
              </p>
            )}
            <div className="dz-actions">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => start(phase.file)}
              >
                Upload and process
              </button>
              <button type="button" className="btn" onClick={reset}>
                Remove
              </button>
            </div>
          </div>
        )}

        {phase.kind === "uploading" && (
          <div className="dz-file">
            <FileChip file={phase.file} />
            <div className="dz-progress" role="status" aria-live="polite">
              <div
                className="progress"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={phase.percent}
                aria-label="Upload progress"
              >
                <i style={{ width: `${phase.percent}%` }} />
              </div>
              <span>
                {phase.percent >= 100
                  ? "Finishing up…"
                  : `Uploading… ${phase.percent}%`}
              </span>
              <button
                type="button"
                className="btn btn-quiet"
                onClick={() => abort.current?.abort()}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {phase.kind === "success" && (
          <div className="dz-outcome dz-good" role="status">
            <span className="dz-mark" aria-hidden="true">
              ✓
            </span>
            <div>
              <strong>{phase.file.name} uploaded</strong>
              <p>Processing has started. Follow its progress below.</p>
            </div>
            <button type="button" className="btn" onClick={reset}>
              Upload another
            </button>
          </div>
        )}
      </div>

      {phase.kind === "error" && (
        <div className="dz-outcome dz-bad" role="alert">
          <span className="dz-mark" aria-hidden="true">
            !
          </span>
          <div>
            <strong>
              {phase.file ? "Upload failed" : "Can't use that file"}
            </strong>
            <p>{phase.message}</p>
          </div>
          {phase.file && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => start(phase.file as File)}
            >
              Try again
            </button>
          )}
          <button type="button" className="btn" onClick={reset}>
            Choose another file
          </button>
        </div>
      )}
    </section>
  );
}

function FileChip({ file }: { file: File }) {
  const extension = file.name.split(".").pop()?.toUpperCase() ?? "VIDEO";
  return (
    <div className="file-chip">
      <span className="file-ext">{extension.slice(0, 4)}</span>
      <div>
        <strong title={file.name}>{file.name}</strong>
        <small>{formatBytes(file.size)}</small>
      </div>
    </div>
  );
}
