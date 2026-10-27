import type { MediaWithJob } from "../api/client";

// Heads-ups for things that have not failed yet but probably will, or will not give the
// result a person expects. Derived from data the API already returns, like workflow.ts.

export interface Warning {
  id: string;
  title: string;
  detail: string;
}

// Mirrors compute_audio_status in packages/contracts: a dub fits when it is within
// max(0.3 s, 15%) of the original line.
const MISMATCH_ABS_MS = 300;
const MISMATCH_REL = 0.15;
// Past this share of the tolerance, a line fits today but a small edit will break it.
const NEAR_LIMIT = 0.8;

// Rough speech rate for dubbed lines. Above it a voice has to rush to fit the slot.
const MAX_CHARS_PER_SECOND = 18;

const WORKER_IDLE_MS = 30_000;
const STALLED_MS = 3 * 60_000;

function tolerance(durationMs: number): number {
  return Math.max(MISMATCH_ABS_MS, MISMATCH_REL * durationMs);
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

export function deriveWarnings(
  item: MediaWithJob,
  now: number = Date.now(),
): Warning[] {
  const { job, segments } = item;
  const warnings: Warning[] = [];

  const idleMs = now - new Date(job.updated_at).getTime();

  if (job.status === "pending" && idleMs > WORKER_IDLE_MS) {
    warnings.push({
      id: "worker-idle",
      title: "The worker may not be running",
      detail:
        "This job has been queued for a while. Check that the pipeline container is up (docker compose ps).",
    });
  }

  if (job.status === "processing" && idleMs > STALLED_MS) {
    warnings.push({
      id: "job-stalled",
      title: "Processing is taking longer than usual",
      detail:
        "The first run downloads speech and translation models, which can take several minutes. If it stays on the same step, check the pipeline logs (docker compose logs pipeline).",
    });
  }

  const untranslated = segments.filter((s) => !s.translated_text?.trim());
  if (untranslated.length > 0) {
    warnings.push({
      id: "untranslated",
      title: `${plural(untranslated.length, "line has", "lines have")} no translation`,
      detail:
        "Dubbed audio can't be generated for them. Add a translation to each before generating.",
    });
  }

  // Not generated yet: guess from the text whether the voice can fit the slot.
  const crowded = segments.filter((s) => {
    const text = s.translated_text?.trim();
    if (!text || s.audio_status !== "no_audio") return false;
    return text.length / (s.duration_ms / 1000) > MAX_CHARS_PER_SECOND;
  });
  if (crowded.length > 0) {
    warnings.push({
      id: "too-long",
      title: `${plural(crowded.length, "line is", "lines are")} probably too long for its slot`,
      detail: `The translation is more than ${MAX_CHARS_PER_SECOND} characters per second of the original line, so the dub will likely come out the wrong length. Shorten the text or widen the line's start and end before generating.`,
    });
  }

  // Generated and fitting, but only just.
  const tight = segments.filter((s) => {
    const dubbed = s.artifact?.duration_ms;
    if (s.audio_status !== "ready" || dubbed == null) return false;
    const limit = tolerance(s.duration_ms);
    return Math.abs(dubbed - s.duration_ms) > limit * NEAR_LIMIT;
  });
  if (tight.length > 0) {
    warnings.push({
      id: "tight-fit",
      title: `${plural(tight.length, "dubbed line is", "dubbed lines are")} close to the timing limit`,
      detail:
        "They fit now, but editing the text or timing is likely to push them out of range.",
    });
  }

  // Approval no longer reflects the audio that would be exported.
  const staleAudio = segments.filter(
    (s) => s.review_status === "approved" && s.audio_status === "outdated",
  );
  if (staleAudio.length > 0) {
    warnings.push({
      id: "stale-audio",
      title: `${plural(staleAudio.length, "approved line has", "approved lines have")} out-of-date audio`,
      detail:
        "The text changed after the audio was made. Regenerate it, or the export will be blocked.",
    });
  }

  return warnings;
}
