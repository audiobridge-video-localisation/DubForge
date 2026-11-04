// Worker failures can carry a tool's whole output (ffmpeg prints its build configuration
// before the actual error). Show the last meaningful line up front and keep the rest
// behind a "details" toggle.
const LONG = 220;

export interface ErrorSummary {
  /** short enough to read at a glance */
  headline: string;
  /** the full text, only when it is worth showing */
  details: string | null;
}

// Known tool failures with a plainer explanation. The full output stays under "details".
const KNOWN_ERRORS: { match: RegExp; headline: string }[] = [
  {
    match: /moov atom not found|Invalid data found when processing input/i,
    headline:
      "This file doesn't look like a valid video. It may be corrupted or incomplete. Try re-exporting it and uploading again.",
  },
  {
    match:
      /does not contain any stream|matches no streams|Stream map .* matches no/i,
    headline:
      "No audio track was found in this video. Upload a file that has sound.",
  },
  {
    match: /No space left on device/i,
    headline: "The server is out of disk space, so the job couldn't finish.",
  },
];

export function summarizeError(
  message: string | null | undefined,
): ErrorSummary {
  const text = (message ?? "").trim();
  if (!text)
    return { headline: "The job stopped before it finished.", details: null };
  const known = KNOWN_ERRORS.find(({ match }) => match.test(text));
  if (known) return { headline: known.headline, details: text };
  if (text.length <= LONG && !text.includes("\n")) {
    return { headline: text, details: null };
  }
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  // Tools print a banner first and the real error somewhere after it (and the worker may
  // cut the message short). Skip banner lines, prefer the first short line that names an
  // error, and drop its "[in#0 @ 0x...]" tag; otherwise fall back to the last line.
  const banner = /version \d|copyright|configuration:|built with|^lib\w+ +\d/i;
  const candidates = lines.filter(
    (line) => line.length <= LONG && !banner.test(line),
  );
  const pick =
    candidates.find((line) =>
      /\berror\b|no such|invalid|cannot|unable|not found|denied/i.test(line),
    ) ??
    candidates.find((line) => /failed/i.test(line)) ??
    lines[lines.length - 1] ??
    text;
  const clean = pick.replace(/^\[[^\]]*\]\s*/, "");
  const headline =
    clean.length <= LONG
      ? clean
      : `…${clean.slice(clean.length - LONG).trim()}`;
  return { headline, details: text };
}
