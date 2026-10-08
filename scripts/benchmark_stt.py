"""Benchmark an STT provider's speed, memory use, and output on a given video.

Usage:
    uv run python scripts/benchmark_stt.py <video_path> [--provider whisper|mock]
        [--model small.en] [--compute-type int8] [--out benchmarks/results.jsonl]
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import psutil

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "pipeline" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "contracts" / "src"))

from dubforge_pipeline.audio import extract_audio  # noqa: E402
from dubforge_pipeline.providers.registry import get_stt_provider  # noqa: E402


@dataclass
class MemorySampler:
    process: psutil.Process
    interval_s: float = 0.2
    peak_rss_mb: float = field(default=0.0)
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = field(default=None)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                rss_mb = self.process.memory_info().rss / (1024 * 1024)
                self.peak_rss_mb = max(self.peak_rss_mb, rss_mb)
            except psutil.Error:
                pass
            self._stop_event.wait(self.interval_s)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()


def get_audio_duration_s(audio_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            audio_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def format_timestamp(seconds_ms: int) -> str:
    total_seconds = seconds_ms / 1000
    minutes = int(total_seconds // 60)
    seconds = total_seconds - minutes * 60
    return f"{minutes:02d}:{seconds:06.3f}"


def write_transcript(path: Path, segments: list[object]) -> None:
    lines = []
    for seg in segments:
        start = format_timestamp(seg.start_ms)  # type: ignore[attr-defined]
        end = format_timestamp(seg.end_ms)  # type: ignore[attr-defined]
        text = seg.text  # type: ignore[attr-defined]
        lines.append(f"[{start} --> {end}] {text}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_path", help="Path to the input video file")
    parser.add_argument("--provider", default="whisper", choices=["whisper", "mock"])
    parser.add_argument("--model", default="small.en")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--out", default="benchmarks/results.jsonl")
    args = parser.parse_args()

    video_path = Path(args.video_path)
    if not video_path.exists():
        raise SystemExit(f"video file not found: {video_path}")

    os.environ["STT_PROVIDER"] = args.provider
    os.environ["WHISPER_MODEL"] = args.model
    os.environ["WHISPER_COMPUTE_TYPE"] = args.compute_type

    process = psutil.Process()
    sampler = MemorySampler(process=process)
    sampler.start()

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            audio_path = str(Path(tmp_dir) / "audio.wav")

            extract_start = time.perf_counter()
            extract_audio(str(video_path), audio_path)
            extract_time_s = time.perf_counter() - extract_start

            audio_duration_s = get_audio_duration_s(audio_path)

            provider = get_stt_provider()

            transcribe_start = time.perf_counter()
            segments = provider.transcribe(audio_path)
            transcribe_time_s = time.perf_counter() - transcribe_start
    finally:
        sampler.stop()

    real_time_factor = (
        transcribe_time_s / audio_duration_s if audio_duration_s > 0 else float("nan")
    )
    confidences = [seg.confidence for seg in segments if seg.confidence is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "video_file": video_path.name,
        "provider": args.provider,
        "model": args.model,
        "compute_type": args.compute_type,
        "device": os.environ.get("WHISPER_DEVICE", "cpu"),
        "cpu_count": os.cpu_count(),
        "audio_duration_s": round(audio_duration_s, 3),
        "extract_time_s": round(extract_time_s, 3),
        "transcribe_time_s": round(transcribe_time_s, 3),
        "real_time_factor": round(real_time_factor, 4),
        "peak_rss_mb": round(sampler.peak_rss_mb, 1),
        "num_segments": len(segments),
        "avg_confidence": round(avg_confidence, 4) if avg_confidence is not None else None,
    }
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    transcript_path = out_path.parent / f"{video_path.stem}_{args.provider}_{args.model}.txt"
    write_transcript(transcript_path, segments)

    print()
    print("Benchmark summary")
    print("-" * 40)
    for key, value in record.items():
        print(f"{key:>18}: {value}")
    print("-" * 40)
    print(f"results appended to: {out_path}")
    print(f"transcript written to: {transcript_path}")


if __name__ == "__main__":
    main()
