import type { ExportJob, MediaWithJob } from "../api/client";
import { detectTargetLanguage } from "./workflow";

// Everything the Export center shows is derived from the project data the API already
// returns. The server enforces the same rule (readiness.py); this explains it.

export type BlockerKind =
  | "needs_changes"
  | "unreviewed"
  | "no_audio"
  | "generating"
  | "failed"
  | "outdated"
  | "mismatch";

export interface Blocker {
  kind: BlockerKind;
  /** 1-based line numbers, as the review table shows them */
  lines: number[];
  /** how to clear it, in one short sentence */
  fix: string;
}

export interface ExportSummary {
  lineCount: number;
  speakerCount: number;
  /** length of the original speech, up to the end of the last line */
  durationMs: number;
  language: string | null;
  voices: string[];
}

export interface ExportCenterState {
  approved: number;
  total: number;
  audioReady: number;
  blockers: Blocker[];
  ready: boolean;
  summary: ExportSummary;
}

export function deriveExportCenter(item: MediaWithJob): ExportCenterState {
  const { segments, approved_count, total_count, usable_audio_count } = item;
  const lines = (match: (s: (typeof segments)[number]) => boolean): number[] =>
    segments
      .map((s, position) => ({ s, position }))
      .filter(({ s }) => match(s))
      .map(({ position }) => position + 1);

  const found: Blocker[] = [];
  const add = (kind: BlockerKind, numbers: number[], fix: string) => {
    if (numbers.length > 0) found.push({ kind, lines: numbers, fix });
  };

  // review problems first, then audio problems: that is the order a person fixes them
  add(
    "needs_changes",
    lines((s) => s.review_status === "needs_changes"),
    "Edit the translation, then approve the line again.",
  );
  add(
    "unreviewed",
    lines((s) => s.review_status === "pending"),
    "Read each line and approve it.",
  );
  add(
    "no_audio",
    lines((s) => s.audio_status === "no_audio"),
    "Use “Generate dubbed audio”.",
  );
  add(
    "generating",
    lines((s) => s.audio_status === "pending"),
    "Wait a moment. This page updates on its own.",
  );
  add(
    "failed",
    lines((s) => s.audio_status === "failed"),
    "Use “Regenerate problem audio”.",
  );
  add(
    "outdated",
    lines((s) => s.audio_status === "outdated"),
    "The text changed after the audio was made. Regenerate it.",
  );
  add(
    "mismatch",
    lines((s) => s.audio_status === "mismatch"),
    "The dub is too long to fit before the next line. Shorten the translation or widen the line, then regenerate.",
  );

  const voices = Array.from(
    new Set(
      segments
        .map((s) => s.artifact?.voice_profile)
        .filter((v): v is string => Boolean(v)),
    ),
  );

  return {
    approved: approved_count,
    total: total_count,
    audioReady: usable_audio_count,
    blockers: found,
    ready:
      total_count > 0 &&
      approved_count === total_count &&
      usable_audio_count === total_count,
    summary: {
      lineCount: total_count,
      speakerCount: new Set(segments.map((s) => s.speaker_label)).size,
      durationMs: segments.reduce((end, s) => Math.max(end, s.end_ms), 0),
      language: detectTargetLanguage([item]),
      voices,
    },
  };
}

const BLOCKER_TITLES: Record<BlockerKind, (n: number) => string> = {
  needs_changes: (n) => `${n} ${n === 1 ? "line needs" : "lines need"} changes`,
  unreviewed: (n) =>
    `${n} ${n === 1 ? "line is" : "lines are"} not approved yet`,
  no_audio: (n) =>
    `${n} ${n === 1 ? "line has" : "lines have"} no dubbed audio`,
  generating: (n) =>
    `${n} ${n === 1 ? "line is" : "lines are"} still being generated`,
  failed: (n) => `Audio failed for ${n} ${n === 1 ? "line" : "lines"}`,
  outdated: (n) => `${n} ${n === 1 ? "line has" : "lines have"} outdated audio`,
  mismatch: (n) => `${n} dubbed ${n === 1 ? "line is" : "lines are"} too long`,
};

export function blockerTitle(blocker: Blocker): string {
  return BLOCKER_TITLES[blocker.kind](blocker.lines.length);
}

/** "Line 3" / "Lines 2, 5 and 9" / "Lines 1, 2, 3, 4, 5 and 7 more" */
export function describeLines(numbers: number[], show = 5): string {
  const label = numbers.length === 1 ? "Line" : "Lines";
  if (numbers.length <= show) {
    if (numbers.length === 1) return `${label} ${numbers[0]}`;
    const head = numbers.slice(0, -1).join(", ");
    return `${label} ${head} and ${numbers[numbers.length - 1]}`;
  }
  return `${label} ${numbers.slice(0, show).join(", ")} and ${numbers.length - show} more`;
}

/**
 * True when a finished export no longer matches the lines: some audio was regenerated
 * after the export started. The file still downloads, but it is the older dub.
 */
export function isExportStale(job: ExportJob, item: MediaWithJob): boolean {
  if (job.status !== "completed") return false;
  const started = new Date(job.created_at).getTime();
  return item.segments.some(
    (s) => s.artifact && new Date(s.artifact.updated_at).getTime() > started,
  );
}
