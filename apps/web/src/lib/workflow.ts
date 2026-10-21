import type {
  Artifact,
  Job,
  MediaWithJob,
  Project,
  Segment,
  SegmentAudioStatus,
} from "../api/client";

// What the app shows about a project is derived from data the API already returns.
// Nothing here is stored or guessed on the server.

export const WORKFLOW_STEPS = [
  "Upload",
  "Process",
  "Review",
  "Dub",
  "Export",
] as const;

export type Tone = "neutral" | "info" | "ok" | "warn" | "danger";

export interface WorkflowState {
  /** index into WORKFLOW_STEPS */
  step: number;
  label: string;
  detail: string;
  tone: Tone;
}

export function isArtifactInFlight(artifact: Artifact | null): boolean {
  return artifact?.status === "pending" || artifact?.status === "processing";
}

export function isAudioProblem(status: SegmentAudioStatus): boolean {
  return status === "failed" || status === "mismatch" || status === "outdated";
}

export function isJobInFlight(job: Job): boolean {
  return job.status === "pending" || job.status === "processing";
}

// The worker reports 10 on start, 30 before audio extraction, 70 before
// transcription + translation and 90 once it is saving segments.
export function stageLabel(job: Job): string {
  if (job.status === "pending") return "Waiting for the worker";
  if (job.status === "failed") return "Stopped";
  if (job.status === "completed") return "Done";
  if (job.progress >= 90) return "Saving segments";
  if (job.progress >= 70) return "Transcribing and translating";
  if (job.progress >= 30) return "Extracting audio";
  return "Starting";
}

/** The most recently uploaded media is the one the project header describes. */
export function primaryMedia(media: MediaWithJob[]): MediaWithJob | undefined {
  return [...media].sort(
    (a, b) =>
      new Date(b.media.created_at).getTime() -
      new Date(a.media.created_at).getTime(),
  )[0];
}

export function deriveWorkflow(item: MediaWithJob | undefined): WorkflowState {
  if (!item) {
    return {
      step: 0,
      label: "Waiting for a video",
      detail: "Upload a video to begin.",
      tone: "neutral",
    };
  }
  const { job, segments, approved_count, total_count, usable_audio_count } =
    item;

  if (job.status === "failed") {
    return {
      step: 1,
      label: "Processing failed",
      detail: job.error_message ?? "The job stopped before it finished.",
      tone: "danger",
    };
  }
  if (job.status === "pending") {
    return {
      step: 1,
      label: "Queued",
      detail: "Waiting for the worker to pick it up.",
      tone: "info",
    };
  }
  if (job.status === "processing") {
    return {
      step: 1,
      label: "Processing",
      detail: `${stageLabel(job)} · ${job.progress}%`,
      tone: "info",
    };
  }
  if (total_count === 0) {
    return {
      step: 1,
      label: "No segments found",
      detail: "Processing finished, but no speech was detected.",
      tone: "warn",
    };
  }
  if (approved_count < total_count) {
    const changes = segments.filter(
      (s) => s.review_status === "needs_changes",
    ).length;
    return {
      step: 2,
      label: changes > 0 ? "Changes requested" : "In review",
      detail: `${approved_count} of ${total_count} lines approved`,
      tone: changes > 0 ? "warn" : "info",
    };
  }
  if (usable_audio_count < total_count) {
    const generating = segments.some((s) => isArtifactInFlight(s.artifact));
    const problems = segments.some((s) => isAudioProblem(s.audio_status));
    return {
      step: 3,
      label: generating
        ? "Generating audio"
        : problems
          ? "Audio needs attention"
          : "Dubbing",
      detail: `${usable_audio_count} of ${total_count} dubbed lines ready`,
      tone: problems && !generating ? "warn" : "info",
    };
  }
  return {
    step: 4,
    label: "Ready to export",
    detail: "Every line is approved and has usable audio.",
    tone: "ok",
  };
}

const LANGUAGE_NAMES: Record<string, string> = { hi: "Hindi", bn: "Bengali" };

// The API has no "target language" field. It shows up in the data in two places: the
// voice profile of generated audio (normally a language code like "hi"), and the script
// of the translated text. Use the first one that is available.
export function detectTargetLanguage(media: MediaWithJob[]): string | null {
  for (const item of media) {
    for (const segment of item.segments) {
      const profile = segment.artifact?.voice_profile?.split("-")[0];
      if (profile && LANGUAGE_NAMES[profile]) return LANGUAGE_NAMES[profile];
    }
  }
  for (const item of media) {
    for (const segment of item.segments) {
      const text = segment.translated_text ?? "";
      if (/[ऀ-ॿ]/.test(text)) return "Hindi";
      if (/[ঀ-৿]/.test(text)) return "Bengali";
    }
  }
  return null;
}

export function lastUpdated(project: Project, media: MediaWithJob[]): Date {
  const times = [new Date(project.created_at).getTime()];
  for (const item of media) {
    times.push(new Date(item.media.created_at).getTime());
    times.push(new Date(item.job.updated_at).getTime());
    for (const segment of item.segments) {
      if (segment.artifact) {
        times.push(new Date(segment.artifact.updated_at).getTime());
      }
    }
  }
  return new Date(Math.max(...times.filter((t) => !Number.isNaN(t))));
}

export function formatTimestamp(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function formatDuration(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

export function relativeTime(date: Date, now = new Date()): string {
  const seconds = Math.round((now.getTime() - date.getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return date.toLocaleDateString();
}

export type ReviewFilter =
  "all" | "pending" | "approved" | "needs_changes" | "processing";

export function matchesFilter(segment: Segment, filter: ReviewFilter): boolean {
  switch (filter) {
    case "all":
      return true;
    case "processing":
      return isArtifactInFlight(segment.artifact);
    default:
      return segment.review_status === filter;
  }
}

export function countByFilter(
  segments: Segment[],
): Record<ReviewFilter, number> {
  return {
    all: segments.length,
    pending: segments.filter((s) => matchesFilter(s, "pending")).length,
    approved: segments.filter((s) => matchesFilter(s, "approved")).length,
    needs_changes: segments.filter((s) => matchesFilter(s, "needs_changes"))
      .length,
    processing: segments.filter((s) => matchesFilter(s, "processing")).length,
  };
}
