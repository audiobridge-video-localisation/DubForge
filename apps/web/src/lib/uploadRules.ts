import { formatBytes } from "./workflow";

// The web proxy refuses bodies over 2 GB (apps/web/nginx.conf: client_max_body_size), and
// the API reads the whole file into memory. Check here so a person hears about it before
// waiting through an upload that cannot work.
export const MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024;
export const LARGE_UPLOAD_BYTES = 500 * 1024 * 1024;

export const VIDEO_EXTENSIONS = [
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

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

/** Why this file can't be uploaded, or null when it can. */
export function validateVideoFile(file: {
  name: string;
  size: number;
  type: string;
}): string | null {
  if (file.size === 0) {
    return "That file is empty (0 bytes). Pick the original video, not a placeholder.";
  }
  const extension = extensionOf(file.name);
  const looksLikeVideo =
    file.type.startsWith("video/") || VIDEO_EXTENSIONS.includes(extension);
  if (!looksLikeVideo) {
    const shown = extension ? `.${extension}` : "no file type";
    return `${shown} files aren't supported. Choose a video: MP4, MOV, MKV or WebM.`;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `That video is ${formatBytes(file.size)}. The limit is ${formatBytes(MAX_UPLOAD_BYTES)}. Compress it or trim it and try again.`;
  }
  return null;
}

/** A heads-up for files that are allowed but likely to be slow. */
export function uploadAdvice(file: { size: number }): string | null {
  if (file.size >= LARGE_UPLOAD_BYTES) {
    return `This is a large file (${formatBytes(file.size)}). It can take a while to upload and process. Keep this tab open.`;
  }
  return null;
}

/** When several files are dropped, only the first is used, and the person should know. */
export function describeSelection(count: number): string | null {
  return count > 1
    ? `You dropped ${count} files. DubForge uses one video at a time, so only the first was picked.`
    : null;
}
