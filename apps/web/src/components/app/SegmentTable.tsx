import { useState } from "react";

import type {
  Segment,
  SegmentAudioStatus,
  SegmentReviewStatus,
  SegmentUpdate,
} from "../../api/client";
import {
  countByFilter,
  formatDuration,
  formatTimestamp,
  isArtifactInFlight,
  matchesFilter,
  type ReviewFilter,
  type Tone,
} from "../../lib/workflow";
import { StatusBadge } from "./StatusBadge";

const REVIEW_LABEL: Record<SegmentReviewStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  needs_changes: "Needs changes",
};
const REVIEW_TONE: Record<SegmentReviewStatus, Tone> = {
  pending: "neutral",
  approved: "ok",
  needs_changes: "warn",
};

const AUDIO_LABEL: Record<SegmentAudioStatus, string> = {
  no_audio: "No audio",
  pending: "Generating",
  failed: "Failed",
  outdated: "Outdated",
  mismatch: "Duration mismatch",
  ready: "Ready",
};
const AUDIO_TONE: Record<SegmentAudioStatus, Tone> = {
  no_audio: "neutral",
  pending: "info",
  failed: "danger",
  outdated: "warn",
  mismatch: "warn",
  ready: "ok",
};

const FILTERS: { key: ReviewFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "needs_changes", label: "Needs changes" },
  { key: "processing", label: "Processing" },
];

interface Draft {
  text: string;
  translated_text: string;
  speaker_label: string;
  start_ms: number;
  end_ms: number;
}

function draftFrom(segment: Segment): Draft {
  return {
    text: segment.text,
    translated_text: segment.translated_text ?? "",
    speaker_label: segment.speaker_label,
    start_ms: segment.start_ms,
    end_ms: segment.end_ms,
  };
}

function diffDraft(segment: Segment, draft: Draft): SegmentUpdate {
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

function closeMenu(button: HTMLElement) {
  const menu = button.closest("details");
  if (menu) menu.open = false;
}

export interface SegmentHandlers {
  onSave: (segmentId: string, patch: SegmentUpdate) => Promise<void>;
  onApprove: (segmentId: string) => Promise<void>;
  onRequestChanges: (segmentId: string) => Promise<void>;
  onRegenerate: (segmentId: string) => Promise<void>;
}

export function SegmentTable({
  segments,
  activeId,
  onSeek,
  ...handlers
}: {
  segments: Segment[];
  /** the line the dub player is currently on */
  activeId: string | null;
  /** present when a dub can be played; makes each line's time a play button */
  onSeek?: (ms: number) => void;
} & SegmentHandlers) {
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const counts = countByFilter(segments);
  const visible = segments.filter((s) => matchesFilter(s, filter));

  return (
    <div className="segments">
      <div className="segments-bar">
        <h3>Transcript and translation</h3>
        <div className="filters" role="group" aria-label="Filter lines">
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className={`chip${filter === key ? " chip-on" : ""}`}
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
            >
              {label}
              <b>{counts[key]}</b>
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="segments-empty" role="status">
          {filter === "processing"
            ? "No lines are generating audio right now."
            : "No lines match this filter."}
        </p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col" className="c-num">
                  #
                </th>
                <th scope="col">Time</th>
                <th scope="col">Duration</th>
                <th scope="col">Speaker</th>
                <th scope="col">Source</th>
                <th scope="col">Translation</th>
                <th scope="col">Review · Audio</th>
                <th scope="col" className="c-act">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visible.map((segment) => (
                <SegmentRow
                  key={segment.id}
                  segment={segment}
                  playing={segment.id === activeId}
                  onSeek={onSeek}
                  {...handlers}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="segments-foot">
        Showing {visible.length} of {segments.length} lines
      </p>
    </div>
  );
}

function SegmentRow({
  segment,
  playing,
  onSeek,
  onSave,
  onApprove,
  onRequestChanges,
  onRegenerate,
}: {
  segment: Segment;
  playing: boolean;
  onSeek?: (ms: number) => void;
} & SegmentHandlers) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const editing = draft !== null;
  const dirty = editing && Object.keys(diffDraft(segment, draft)).length > 0;
  const invalid =
    editing && (draft.start_ms < 0 || draft.start_ms >= draft.end_ms);
  const generating = isArtifactInFlight(segment.artifact);

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    if (!draft || invalid || !dirty) return;
    setSaving(true);
    setError(null);
    try {
      await onSave(segment.id, diffDraft(segment, draft));
      setDraft(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const audioNote =
    segment.audio_status === "mismatch" && segment.artifact?.duration_ms != null
      ? `Expected ${formatDuration(segment.duration_ms)}, got ${formatDuration(segment.artifact.duration_ms)}`
      : segment.audio_status === "failed"
        ? (segment.artifact?.error_message ?? null)
        : null;

  return (
    <>
      <tr
        className={`row row-${segment.review_status}${editing ? " row-editing" : ""}${playing ? " row-playing" : ""}`}
        aria-current={playing ? "true" : undefined}
      >
        <td className="c-num" data-label="#">
          {segment.index + 1}
        </td>
        <td className="c-time" data-label="Time">
          {onSeek ? (
            <button
              type="button"
              className="time-btn"
              aria-label={`Play line ${segment.index + 1} from ${formatTimestamp(segment.start_ms)}`}
              onClick={() => onSeek(segment.start_ms)}
            >
              <span aria-hidden="true">{playing ? "♪" : "▶"}</span>
              {formatTimestamp(segment.start_ms)}–
              {formatTimestamp(segment.end_ms)}
            </button>
          ) : (
            <>
              {formatTimestamp(segment.start_ms)}–
              {formatTimestamp(segment.end_ms)}
            </>
          )}
        </td>
        <td className="c-dur" data-label="Duration">
          {formatDuration(segment.duration_ms)}
        </td>
        <td className="c-speaker" data-label="Speaker">
          <span className="speaker">{segment.speaker_label}</span>
        </td>
        <td className="c-text" data-label="Source">
          {segment.text}
        </td>
        <td className="c-text c-tr" data-label="Translation">
          {segment.translated_text ?? <em>Not translated</em>}
        </td>
        <td className="c-status" data-label="Status">
          <div className="status-stack">
            <StatusBadge tone={REVIEW_TONE[segment.review_status]}>
              {REVIEW_LABEL[segment.review_status]}
            </StatusBadge>
            <StatusBadge
              tone={AUDIO_TONE[segment.audio_status]}
              pulse={segment.audio_status === "pending"}
            >
              Audio: {AUDIO_LABEL[segment.audio_status].toLowerCase()}
            </StatusBadge>
          </div>
          {audioNote && <small className="audio-note">{audioNote}</small>}
        </td>
        <td className="c-act">
          {!editing && (
            <div className="row-actions">
              <button
                type="button"
                className="btn btn-sm btn-primary"
                disabled={busy !== null || segment.review_status === "approved"}
                onClick={() => run("approve", () => onApprove(segment.id))}
              >
                {busy === "approve" ? "Approving…" : "Approve"}
              </button>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() => {
                  setDraft(draftFrom(segment));
                  setError(null);
                }}
              >
                Edit
              </button>
              <details className="more">
                <summary className="btn btn-sm" aria-label="More actions">
                  ⋯
                </summary>
                <div className="more-menu">
                  <button
                    type="button"
                    disabled={
                      busy !== null || segment.review_status === "needs_changes"
                    }
                    onClick={(event) => {
                      closeMenu(event.currentTarget);
                      void run("changes", () => onRequestChanges(segment.id));
                    }}
                  >
                    Request changes
                  </button>
                  <button
                    type="button"
                    disabled={busy !== null || generating}
                    onClick={(event) => {
                      closeMenu(event.currentTarget);
                      void run("regen", () => onRegenerate(segment.id));
                    }}
                  >
                    {generating ? "Generating audio…" : "Regenerate audio"}
                  </button>
                </div>
              </details>
            </div>
          )}
        </td>
      </tr>

      {(error || (editing && draft)) && (
        <tr className="row-panel">
          <td colSpan={8}>
            {error && (
              <p className="inline-error" role="alert">
                {error}
              </p>
            )}
            {editing && draft && (
              <form
                className="edit"
                onSubmit={(event) => {
                  event.preventDefault();
                  void save();
                }}
                onKeyDown={(event) => {
                  if (event.key === "Escape") setDraft(null);
                  if (
                    event.key === "Enter" &&
                    (event.metaKey || event.ctrlKey)
                  ) {
                    event.preventDefault();
                    void save();
                  }
                }}
              >
                <label>
                  <span>Source text</span>
                  <textarea
                    rows={3}
                    value={draft.text}
                    onChange={(e) =>
                      setDraft({ ...draft, text: e.target.value })
                    }
                  />
                </label>
                <label>
                  <span>Translation</span>
                  <textarea
                    rows={3}
                    autoFocus
                    value={draft.translated_text}
                    onChange={(e) =>
                      setDraft({ ...draft, translated_text: e.target.value })
                    }
                  />
                </label>
                <div className="edit-meta">
                  <label>
                    <span>Speaker</span>
                    <input
                      value={draft.speaker_label}
                      onChange={(e) =>
                        setDraft({ ...draft, speaker_label: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    <span>Start (ms)</span>
                    <input
                      type="number"
                      min={0}
                      value={draft.start_ms}
                      onChange={(e) =>
                        setDraft({ ...draft, start_ms: Number(e.target.value) })
                      }
                    />
                  </label>
                  <label>
                    <span>End (ms)</span>
                    <input
                      type="number"
                      min={0}
                      value={draft.end_ms}
                      onChange={(e) =>
                        setDraft({ ...draft, end_ms: Number(e.target.value) })
                      }
                    />
                  </label>
                </div>
                {invalid && (
                  <p className="inline-error" role="alert">
                    Start must be 0 or greater, and before the end.
                  </p>
                )}
                <p className="edit-note">
                  Saving a change sends this line back to pending review and
                  marks its audio outdated.
                </p>
                <div className="edit-actions">
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={saving || invalid || !dirty}
                  >
                    {saving ? "Saving…" : "Save changes"}
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={saving}
                    onClick={() => setDraft(null)}
                  >
                    Cancel
                  </button>
                  <span className="edit-hint">
                    Esc to cancel · Ctrl/⌘ + Enter to save
                  </span>
                </div>
              </form>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
