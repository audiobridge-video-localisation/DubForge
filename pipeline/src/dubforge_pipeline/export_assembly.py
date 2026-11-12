import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dubforge_contracts.models import MAX_VIDEO_SLOWDOWN

# Never speed speech up by more than this. Past it the video behind the line is slowed
# instead (up to MAX_VIDEO_SLOWDOWN), and past that its last frame is held.
MAX_ATEMPO = 1.25
# Up to this much faster, a voice sounds natural: only the audio changes and the video is
# left alone. Past it, speech and picture share the change (see _fit_window).
MAX_AUDIO_ONLY_TEMPO = 1.2
# A dub that ends well before its line leaves the speaker's mouth moving in silence, so it
# is slowed toward the line's length, but never below this (slower starts to drawl).
MIN_TEMPO = 0.85
# A dub filling at least this share of its line is left alone: the gap is not noticeable.
UNDERRUN_TOLERANCE = 0.95
# A trimmed clip shorter than this is treated as silence (mock voices are silent) and the
# untrimmed clip is used as it is.
MIN_TRIMMED_MS = 100
# Quieter than this counts as silence at the start and end of a dubbed clip.
SILENCE_THRESHOLD_DB = -45


@dataclass(frozen=True)
class VideoPiece:
    """A stretch of the source video and how it plays in the export."""

    source_start_ms: int
    source_end_ms: int
    slowdown: float = 1.0
    freeze_ms: int = 0

    @property
    def output_ms(self) -> int:
        return round((self.source_end_ms - self.source_start_ms) * self.slowdown) + self.freeze_ms

    @property
    def changes_video(self) -> bool:
        return self.slowdown > 1.0 or self.freeze_ms > 0


@dataclass(frozen=True)
class ClipPlacement:
    """Where a dubbed clip plays on the export's timeline, and how fast."""

    start_ms: int
    tempo: float
    end_ms: int
    # when the line's subtitle should disappear: the end of the speech or of the clip
    subtitle_end_ms: int


@dataclass(frozen=True)
class Timeline:
    pieces: list[VideoPiece]
    clips: list[ClipPlacement]

    @property
    def duration_ms(self) -> int:
        return sum(piece.output_ms for piece in self.pieces)

    @property
    def changes_video(self) -> bool:
        return any(piece.changes_video for piece in self.pieces)


def _fit_window(audio_ms: int, window_ms: int, speech_ms: int) -> tuple[float, float, int]:
    """(tempo, video slowdown, frozen ms) that make `audio_ms` of dub fit the window.

    `window_ms` is all the time the line has (up to the next line); `speech_ms` is how
    long the original speaker talked. A short dub is slowed a little toward `speech_ms`.
    A long one is sped up alone while that still sounds natural; past that the change is
    shared evenly between faster speech and slower video (each by the square root of
    what is needed), so neither is pushed hard. Whatever both caps cannot cover is held
    as a still frame.
    """
    if audio_ms <= window_ms:
        if 0 < audio_ms < speech_ms * UNDERRUN_TOLERANCE:
            return max(audio_ms / speech_ms, MIN_TEMPO), 1.0, 0
        return 1.0, 1.0, 0
    if window_ms <= 0:
        return MAX_ATEMPO, 1.0, math.ceil(audio_ms / MAX_ATEMPO)
    need = audio_ms / window_ms
    if need <= MAX_AUDIO_ONLY_TEMPO:
        return need, 1.0, 0
    tempo = min(math.sqrt(need), MAX_ATEMPO)
    played_ms = audio_ms / tempo
    slowdown = min(played_ms / window_ms, MAX_VIDEO_SLOWDOWN)
    freeze_ms = max(0, math.ceil(played_ms - window_ms * slowdown))
    return tempo, slowdown, freeze_ms


def plan_timeline(segments: list[tuple[int, int, int]], total_duration_ms: int) -> Timeline:
    """Lay out the export so every dubbed clip fits, without cutting or overlapping audio.

    `segments` holds (start_ms, end_ms, audio_duration_ms) in any order; `clips` comes
    back in the same order. Each line owns the video from its start to the next line's
    start (the video's end for the last one). A clip longer than that window is sped up,
    the window's video is slowed, and any remainder holds the window's last frame (see
    _fit_window). So the export always fits; the price is a slightly longer video where
    a line ran long. A clip much shorter than its line is slowed slightly to fill it.
    """
    total_ms = max(total_duration_ms, 0)
    order = sorted(range(len(segments)), key=lambda i: segments[i][0])
    starts = [min(max(segments[i][0], 0), total_ms) for i in order]

    pieces: list[VideoPiece] = []
    clips: list[ClipPlacement | None] = [None] * len(segments)
    lead_end_ms = starts[0] if starts else total_ms
    if lead_end_ms > 0:
        pieces.append(VideoPiece(0, lead_end_ms))
    cursor_ms = sum(piece.output_ms for piece in pieces)

    for position, index in enumerate(order):
        window_start_ms = starts[position]
        window_end_ms = starts[position + 1] if position + 1 < len(order) else total_ms
        window_ms = window_end_ms - window_start_ms
        _start_ms, end_ms, audio_ms = segments[index]
        line_ms = max(min(end_ms, window_end_ms) - window_start_ms, 0)

        tempo, slowdown, freeze_ms = _fit_window(audio_ms, window_ms, line_ms)
        piece = VideoPiece(window_start_ms, window_end_ms, slowdown, freeze_ms)
        played_ms = round(audio_ms / tempo)
        speech_ms = round(line_ms * slowdown)
        clips[index] = ClipPlacement(
            start_ms=cursor_ms,
            tempo=tempo,
            end_ms=cursor_ms + played_ms,
            subtitle_end_ms=cursor_ms + min(max(played_ms, speech_ms), piece.output_ms),
        )
        if piece.output_ms > 0:
            pieces.append(piece)
        cursor_ms += piece.output_ms

    return Timeline(pieces=pieces, clips=[clip for clip in clips if clip is not None])


def _merge_unchanged(pieces: list[VideoPiece]) -> list[VideoPiece]:
    """Join neighbouring pieces that play at normal speed, so they encode as one."""
    merged: list[VideoPiece] = []
    for piece in pieces:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and not previous.changes_video
            and not piece.changes_video
            and previous.source_end_ms == piece.source_start_ms
        ):
            merged[-1] = VideoPiece(previous.source_start_ms, piece.source_end_ms)
        else:
            merged.append(piece)
    return merged


def _run(cmd: list[str], timeout_s: int) -> subprocess.CompletedProcess[str]:
    tool = cmd[0]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"{tool} not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{tool} timed out after {timeout_s}s") from exc
    if result.returncode != 0:
        raise RuntimeError(f"{tool} failed: {result.stderr}")
    return result


def probe_frame_rate(path: str, timeout_s: int = 60) -> float:
    """Frames per second of a video's first video stream."""
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=avg_frame_rate,r_frame_rate",
            "-of",
            "json",
            path,
        ],
        timeout_s,
    )
    streams = json.loads(result.stdout).get("streams") or []
    if not streams:
        raise RuntimeError("no video stream found")
    for key in ("avg_frame_rate", "r_frame_rate"):
        numerator, _, denominator = str(streams[0].get(key, "0/0")).partition("/")
        try:
            rate = float(numerator) / float(denominator or 1)
        except (ValueError, ZeroDivisionError):
            continue
        if rate > 0:
            return rate
    raise RuntimeError("could not read the video frame rate")


def trim_silence(input_path: str, output_path: str, timeout_s: int = 120) -> str:
    """Cut the quiet at the start and end of a dubbed clip, so it only takes the time
    the words need. Silence inside the clip (pauses between words) is kept."""
    edge = f"silenceremove=start_periods=1:start_threshold={SILENCE_THRESHOLD_DB}dB:detection=peak"
    _run(
        ["ffmpeg", "-y", "-i", input_path, "-af", f"{edge},areverse,{edge},areverse", output_path],
        timeout_s,
    )
    if not Path(output_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_path


def build_timeline_video(
    video_path: str,
    pieces: list[VideoPiece],
    work_dir: str,
    output_path: str,
    timeout_s: int = 1800,
) -> str:
    """Re-cut the video (no audio) to the export timeline: slowed pieces play slower
    and frozen time repeats the piece's last frame.

    Each piece is encoded on its own and the pieces are joined, so memory stays flat
    for long videos. Every piece gets an exact frame count taken from the running
    total, so the video cannot drift away from the dub track.
    """
    fps = probe_frame_rate(video_path)
    work = Path(work_dir)
    listing: list[str] = []
    elapsed_ms = 0
    for number, piece in enumerate(_merge_unchanged(pieces)):
        frames_before = round(elapsed_ms * fps / 1000)
        elapsed_ms += piece.output_ms
        frames = round(elapsed_ms * fps / 1000) - frames_before
        if frames <= 0:
            continue
        # pad generously, then stop at the exact frame count
        pad_s = piece.freeze_ms / 1000 + 1
        filters = (
            f"setpts=(PTS-STARTPTS)*{piece.slowdown:.6f},"
            f"tpad=stop_mode=clone:stop_duration={pad_s:.3f},"
            f"fps={fps:.6f},format=yuv420p"
        )
        part = work / f"piece_{number:04d}.mp4"
        source_s = (piece.source_end_ms - piece.source_start_ms) / 1000
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{piece.source_start_ms / 1000:.3f}",
            "-t",
            f"{max(source_s, 0.001):.3f}",
            "-i",
            video_path,
            "-an",
            "-sn",
            "-vf",
            filters,
            "-frames:v",
            str(frames),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            str(part),
        ]
        _run(cmd, timeout_s)
        listing.append(f"file '{part.as_posix()}'")

    if not listing:
        raise RuntimeError("the export timeline is empty")
    list_path = work / "pieces.txt"
    list_path.write_text("\n".join(listing) + "\n")
    _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            output_path,
        ],
        timeout_s,
    )
    if not Path(output_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_path


def probe_duration_ms(path: str, timeout_s: int = 60) -> int:
    """Return a media file's duration in milliseconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffprobe not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffprobe timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    duration_s = float(json.loads(result.stdout)["format"]["duration"])
    return round(duration_s * 1000)


def apply_tempo(input_path: str, output_path: str, tempo: float, timeout_s: int = 600) -> str:
    """Speed audio up (tempo > 1) or down with ffmpeg's pitch-preserving atempo filter."""
    if tempo <= 0:
        raise ValueError(f"tempo must be > 0, got {tempo}")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-filter:a",
        f"atempo={tempo:.4f}",
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not Path(output_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_path


def build_dub_audio_track(
    segment_audio: list[tuple[int, str]],
    total_duration_ms: int,
    output_wav_path: str,
    timeout_s: int = 600,
) -> str:
    """Build one continuous mono 16kHz WAV spanning total_duration_ms, with
    each segment's audio placed at its start_ms offset.

    Uses a silent base track (anullsrc, trimmed to total_duration_ms via its
    own `d=` parameter) mixed with every segment clip delayed to its offset
    via the `adelay` filter, combined with `amix` anchored to the silent
    base track's duration. Clips never overlap, so they are summed at full
    volume (`normalize=0`); amix would otherwise divide every clip by the number
    of lines, making long videos quieter.
    """
    total_duration_s = total_duration_ms / 1000
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=mono:sample_rate=16000:d={total_duration_s}",
    ]
    for _, audio_path in segment_audio:
        cmd += ["-i", audio_path]

    filter_parts = []
    mix_inputs = ["[0:a]"]
    for index, (start_ms, _) in enumerate(segment_audio, start=1):
        label = f"d{index}"
        filter_parts.append(f"[{index}:a]adelay={start_ms}:all=1[{label}]")
        mix_inputs.append(f"[{label}]")
    filter_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:normalize=0[aout]"
    )
    filter_complex = ";".join(filter_parts)

    cmd += [
        "-filter_complex",
        filter_complex,
        "-map",
        "[aout]",
        "-ac",
        "1",
        "-ar",
        "16000",
        output_wav_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not Path(output_wav_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_wav_path


def encode_mp3(wav_path: str, output_mp3_path: str, timeout_s: int = 600) -> str:
    """Encode a WAV file to MP3 (libmp3lame)."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        wav_path,
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "192k",
        output_mp3_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not Path(output_mp3_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_mp3_path


def mux_mp4(
    video_path: str,
    dub_audio_wav_path: str,
    output_mp4_path: str,
    timeout_s: int = 600,
    subtitles_path: str | None = None,
    subtitle_language: str | None = None,
) -> str:
    """Mux a dub audio track onto the video, replacing its audio entirely. The video
    stream is copied untouched (no re-encode). An SRT file, if given, is added as a
    subtitle track the viewer can switch on."""
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", dub_audio_wav_path]
    if subtitles_path is not None:
        cmd += ["-i", subtitles_path]
    cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    if subtitles_path is None:
        cmd += ["-shortest"]
    else:
        # -shortest would also stop at the last subtitle, so give the length outright
        length_ms = min(probe_duration_ms(video_path), probe_duration_ms(dub_audio_wav_path))
        cmd += ["-map", "2:s:0", "-c:s", "mov_text", "-t", f"{length_ms / 1000:.3f}"]
        if subtitle_language:
            cmd += ["-metadata:s:s:0", f"language={subtitle_language}"]
    cmd += [
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        output_mp4_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except FileNotFoundError as exc:
        raise RuntimeError(f"ffmpeg not found: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffmpeg timed out after {timeout_s}s") from exc

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    if not Path(output_mp4_path).exists():
        raise RuntimeError("ffmpeg reported success but output file is missing")
    return output_mp4_path
