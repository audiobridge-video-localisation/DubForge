import { useEffect, useId, useRef, useState } from "react";

import type { UploadOptions } from "../../api/client";
import { formatBytes } from "../../lib/workflow";

const VIDEO_EXTENSIONS = [
  "mp4",
  "mov",
  "m4v",
  "mkv",
  "webm",
  "avi",
  "mpg",
  "mpeg",
  "wmv",
  "flv",
  "3gp",
];

function validate(file: File): string | null {
  if (file.size === 0) return "That file is empty.";
  const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (
    !file.type.startsWith("video/") &&
    !VIDEO_EXTENSIONS.includes(extension)
  ) {
    return "That doesn't look like a video file. Choose an MP4, MOV, MKV or WebM.";
  }
  return null;
}

type Phase =
  | { kind: "idle" }
  | { kind: "ready"; file: File }
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

  function choose(file: File | undefined) {
    if (!file) return;
    const problem = validate(file);
    setPhase(
      problem
        ? { kind: "error", file: null, message: problem }
        : { kind: "ready", file },
    );
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
        setPhase({ kind: "ready", file });
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
          if (!busy) choose(event.dataTransfer.files[0]);
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
          onChange={(event) => choose(event.target.files?.[0])}
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
              MP4, MOV, MKV, WebM and most other video formats · spoken audio
              should be English
            </span>
          </label>
        )}

        {phase.kind === "ready" && (
          <div className="dz-file">
            <FileChip file={phase.file} />
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
