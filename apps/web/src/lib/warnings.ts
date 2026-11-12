import type { MediaWithJob } from "../api/client";

// Heads-ups for things that have not failed yet but probably will, or will not give the
// result a person expects. Only things a person should act on: a line that fits (even one
// the export quietly speeds up or slows down for) gets no warning. Derived from data the API already returns, like workflow.ts.

export interface Warning {
  id: string;
  title: string;
  detail: string;
}

// Rough speech rate for dubbed lines. Above it a voice has to rush to fit the slot.
const MAX_CHARS_PER_SECOND = 18;

const WORKER_IDLE_MS = 30_000;
const STALLED_MS = 3 * 60_000;
// Mirrors job_stall_retry_seconds in the API: past this a silent job may be retried by hand.
export const STALL_RETRY_MS = 5 * 60_000;

/** A queued or running job that has said nothing for long enough to be treated as interrupted. */
export function canRetryStalledJob(
  job: MediaWithJob["job"],
  now: number = Date.now(),
): boolean {
  const inFlight = job.status === "pending" || job.status === "processing";
  return inFlight && now - new Date(job.updated_at).getTime() > STALL_RETRY_MS;
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
        "The first run downloads speech and translation models, which can take several minutes. If nothing changes for a few more minutes the job may have been interrupted (for example by a restart), and a Retry button will appear.",
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
