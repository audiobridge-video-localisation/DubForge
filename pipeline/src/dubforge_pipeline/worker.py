import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx
import redis

from dubforge_contracts.export import segments_to_srt
from dubforge_contracts.models import (
    ARTIFACT_QUEUE_KEY,
    EXPORT_QUEUE_KEY,
    JOB_QUEUE_KEY,
    ArtifactCallbackUpdate,
    ArtifactQueueMessage,
    ArtifactStatus,
    ExportJobCallbackUpdate,
    ExportJobQueueMessage,
    ExportKind,
    JobCallbackUpdate,
    JobQueueMessage,
    JobStatus,
    Segment,
    SpeakerSegment,
    TranscriptSegment,
    remaining_speedup,
)
from dubforge_pipeline.audio import extract_audio, wav_duration_ms
from dubforge_pipeline.auto_shorten import CANDIDATES_TO_SEARCH, shorter_alternatives
from dubforge_pipeline.background import separate_background, voice_path
from dubforge_pipeline.export_assembly import (
    MIN_TRIMMED_MS,
    VideoPiece,
    apply_tempo,
    build_dub_audio_track,
    build_timeline_background,
    build_timeline_video,
    dub_gain_db,
    encode_mp3,
    mix_with_background,
    mux_mp4,
    plan_timeline,
    probe_duration_ms,
    trim_silence,
)
from dubforge_pipeline.logging_config import configure_logging
from dubforge_pipeline.providers.assemblyai import transcribe_with_diarization
from dubforge_pipeline.providers.base import TranslationProvider, TTSProvider
from dubforge_pipeline.providers.mock import MockDiarizationProvider
from dubforge_pipeline.providers.registry import (
    get_stt_provider,
    get_translation_provider,
    get_tts_provider,
)
from dubforge_pipeline.segments import combine_segments, translate_segments
from dubforge_pipeline.speech_rate import get_ms_per_char, record_take
from dubforge_pipeline.timing import merge_short_segments

logger = logging.getLogger(__name__)

_ARTIFACTS_SUBDIR = "artifacts"
_EXPORTS_SUBDIR = "exports"
# ISO 639-2 codes for the MP4 subtitle track's language tag.
_SUBTITLE_LANGUAGE = {"hi": "hin", "bn": "ben"}

_translator_cache: TranslationProvider | None = None
_tts_provider_cache: TTSProvider | None = None


def _report(
    client: httpx.Client,
    api_base_url: str,
    job_id: str,
    status: JobStatus,
    progress: int | None = None,
    error_message: str | None = None,
) -> None:
    payload = JobCallbackUpdate(status=status, progress=progress, error_message=error_message)
    try:
        response = client.patch(
            f"{api_base_url}/internal/jobs/{job_id}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to report status for job %s", job_id)


def _get_transcription(audio_path: str) -> tuple[list[TranscriptSegment], list[SpeakerSegment]]:
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if api_key:
        return transcribe_with_diarization(audio_path, api_key)
    # AssemblyAI alone provides diarization; the registry's providers
    # (mock/whisper, selected via STT_PROVIDER) only do transcription, so
    # diarization still falls back to the mock in that case.
    return (
        get_stt_provider().transcribe(audio_path),
        MockDiarizationProvider().diarize(audio_path),
    )


def _get_translator() -> TranslationProvider:
    # Heavy models (e.g. NLLB) are loaded on first use by the provider
    # itself; cache the provider instance so that load happens once per
    # worker process rather than once per job.
    global _translator_cache
    if _translator_cache is None:
        _translator_cache = get_translation_provider()
    return _translator_cache


def _get_tts_provider() -> TTSProvider:
    # Same rationale as _get_translator: cache so heavy models (e.g. MMS)
    # load once per worker process rather than once per artifact.
    global _tts_provider_cache
    if _tts_provider_cache is None:
        _tts_provider_cache = get_tts_provider()
    return _tts_provider_cache


def _voice_key(lang: str) -> str:
    """What the learned speech rate is filed under: a voice speaks at its own pace."""
    return f"{type(_get_tts_provider()).__name__}:{lang}"


def reset_provider_cache() -> None:
    """Test hook: clear cached providers so tests can swap env/providers freely."""
    global _translator_cache, _tts_provider_cache
    _translator_cache = None
    _tts_provider_cache = None


def _get_target_lang() -> str:
    raw = os.environ.get("TARGET_LANGS", "hi")
    langs = [lang.strip() for lang in raw.split(",") if lang.strip()]
    if not langs:
        langs = ["hi"]
    if len(langs) > 1:
        logger.warning(
            "TARGET_LANGS=%s configures multiple languages, but each segment stores a "
            "single translated_text; only using the first language: %s",
            raw,
            langs[0],
        )
    return langs[0]


def _persist_artifact_audio(audio_path: str, storage_root: str, artifact_id: str) -> str:
    """Move a TTS provider's output into the shared storage volume so the
    api process (and later, export assembly) can find it after this
    container exits. Returns a path relative to storage_root, mirroring
    Media.storage_path's convention.

    Raises if the source file doesn't exist: every provider, including the
    mock, is expected to actually write real bytes (see providers/mock.py),
    so a missing file here means something upstream is broken, not a
    provider-specific quirk to silently paper over.
    """
    source = Path(audio_path)
    if not source.exists():
        raise RuntimeError(f"TTS provider reported audio_path={audio_path!r} but it does not exist")
    artifacts_dir = Path(storage_root) / _ARTIFACTS_SUBDIR
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix or ".wav"
    destination = artifacts_dir / f"{artifact_id}{suffix}"
    shutil.move(str(source), str(destination))
    return destination.relative_to(Path(storage_root)).as_posix()


def _submit_segments(
    client: httpx.Client, api_base_url: str, media_id: str, segments: list[Segment]
) -> None:
    response = client.put(
        f"{api_base_url}/internal/media/{media_id}/segments",
        json=[segment.model_dump(mode="json") for segment in segments],
    )
    response.raise_for_status()


def _report_artifact(
    client: httpx.Client,
    api_base_url: str,
    artifact_id: str,
    status: ArtifactStatus,
    audio_path: str | None = None,
    duration_ms: int | None = None,
    voice_profile: str | None = None,
    speedup: float | None = None,
    error_message: str | None = None,
    translated_text: str | None = None,
) -> None:
    payload = ArtifactCallbackUpdate(
        status=status,
        audio_path=audio_path,
        duration_ms=duration_ms,
        voice_profile=voice_profile,
        speedup=speedup,
        error_message=error_message,
        translated_text=translated_text,
    )
    try:
        response = client.patch(
            f"{api_base_url}/internal/artifacts/{artifact_id}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to report status for artifact %s", artifact_id)


def process_job(
    client: httpx.Client, api_base_url: str, storage_root: str, message: JobQueueMessage
) -> None:
    job_id = str(message.job_id)
    _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=10)
    try:
        input_path = str(Path(storage_root) / message.storage_path)
        output_path = f"{input_path}.wav"
        _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=30)
        extract_audio(input_path, output_path)

        _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=70)
        transcripts, speakers = _get_transcription(output_path)

        min_segment_ms = int(os.environ.get("MIN_SEGMENT_MS", "500"))
        merged_transcripts = merge_short_segments(transcripts, min_duration_ms=min_segment_ms)
        logger.info(
            "Job %s: merged %d transcript segments into %d (min_duration_ms=%d)",
            job_id,
            len(transcripts),
            len(merged_transcripts),
            min_segment_ms,
        )

        segments = combine_segments(merged_transcripts, speakers)
        src_lang = os.environ.get("SOURCE_LANG", "en")
        tgt_lang = _get_target_lang()
        segments = translate_segments(
            segments,
            _get_translator(),
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            # pick translations that the voice can say in the time each line has
            ms_per_char=get_ms_per_char(storage_root, _voice_key(tgt_lang)),
        )

        _report(client, api_base_url, job_id, JobStatus.PROCESSING, progress=90)
        _submit_segments(client, api_base_url, str(message.media_id), segments)
    except Exception as exc:  # defensive: never let a bad job crash the worker loop
        logger.exception("Job %s failed", job_id)
        _report(client, api_base_url, job_id, JobStatus.FAILED, error_message=str(exc))
        return
    _report(client, api_base_url, job_id, JobStatus.COMPLETED, progress=100)


@dataclass
class _Take:
    """One synthesised version of a line: the audio, how long it is, and the wording it says."""

    audio_path: str
    duration_ms: int
    text: str
    # how much the voice sped it up (see MAX_SPEEDUP); export may only add what is left
    speedup: float = 1.0


def _trim_take(audio_path: str, duration_ms: int) -> tuple[str, int]:
    """Cut the silence at both ends of a fresh take. Keeps the take as it is when trimming
    fails or leaves (almost) nothing, e.g. a silent mock voice."""
    source = Path(audio_path)
    trimmed = source.with_name(f"{source.stem}.trim.wav")
    try:
        trim_silence(audio_path, str(trimmed))
        trimmed_ms = wav_duration_ms(str(trimmed))
    except Exception:
        logger.warning("Could not trim silence from %s; keeping it as is", audio_path)
        trimmed.unlink(missing_ok=True)
        return audio_path, duration_ms
    if trimmed_ms < MIN_TRIMMED_MS:
        trimmed.unlink(missing_ok=True)
        return audio_path, duration_ms
    source.unlink(missing_ok=True)
    return str(trimmed), trimmed_ms


def _synthesize_take(
    text: str, message: ArtifactQueueMessage, voice_profile: str, storage_root: str
) -> _Take:
    result = _get_tts_provider().synthesize(
        text,
        voice_profile=voice_profile,
        target_duration_ms=message.target_duration_ms,
        speaker_index=message.speaker_index,
        voice_gender=message.voice_gender,
    )
    # judge (and learn from) the speech itself, not the silence voices add around it
    audio_path, duration_ms = _trim_take(result.audio_path, result.actual_duration_ms)
    if result.speech_rate is not None:
        record_take(
            storage_root,
            _voice_key(voice_profile),
            text,
            duration_ms,
            result.speech_rate,
        )
    # Any speed-up still needed happens at export, within what is left of MAX_SPEEDUP.
    return _Take(
        audio_path=audio_path,
        duration_ms=duration_ms,
        text=text,
        speedup=result.speech_rate or 1.0,
    )


def _fits(take: _Take, room_ms: int) -> bool:
    """Whether export can speed the take into its room without touching the video."""
    return take.duration_ms <= room_ms * remaining_speedup(take.speedup)


def _discard(take: _Take) -> None:
    Path(take.audio_path).unlink(missing_ok=True)


def _try_shorter_wordings(
    take: _Take, message: ArtifactQueueMessage, voice_profile: str, storage_root: str
) -> _Take:
    """The dub still does not fit even sped up: try shorter wordings of the same line.

    Returns the first take that fits, else whichever take is shortest (the original included).
    """
    assert message.target_duration_ms is not None and message.source_text is not None
    room_ms = message.target_duration_ms
    try:
        candidates = _get_translator().translate_candidates(
            message.source_text,
            os.environ.get("SOURCE_LANG", "en"),
            voice_profile,
            count=CANDIDATES_TO_SEARCH,
        )
    except Exception:  # the original take is still usable; it just stays flagged
        logger.warning("could not look for a shorter wording", exc_info=True)
        return take

    best = take
    ms_per_char = get_ms_per_char(storage_root, _voice_key(voice_profile))
    for wording in shorter_alternatives(candidates, take.text, room_ms, ms_per_char):
        attempt = _synthesize_take(wording, message, voice_profile, storage_root)
        if _fits(attempt, room_ms):
            _discard(best)
            return attempt
        if attempt.duration_ms < best.duration_ms:
            _discard(best)
            best = attempt
        else:
            _discard(attempt)
    return best


def process_artifact(
    client: httpx.Client, api_base_url: str, storage_root: str, message: ArtifactQueueMessage
) -> None:
    artifact_id = str(message.artifact_id)
    _report_artifact(client, api_base_url, artifact_id, ArtifactStatus.PROCESSING)

    if not message.text.strip():
        logger.warning("Artifact %s has empty text; skipping synthesis", artifact_id)
        _report_artifact(
            client, api_base_url, artifact_id, ArtifactStatus.FAILED, error_message="empty text"
        )
        return

    try:
        voice_profile = _get_target_lang()
        take = _synthesize_take(message.text, message, voice_profile, storage_root)
        if (
            message.may_rewrite
            and message.source_text
            and message.target_duration_ms is not None
            and not _fits(take, message.target_duration_ms)
        ):
            take = _try_shorter_wordings(take, message, voice_profile, storage_root)
            if take.text != message.text:
                logger.info(
                    "Artifact %s: shortened %r to %r to fit its room",
                    artifact_id,
                    message.text,
                    take.text,
                )
        relative_audio_path = _persist_artifact_audio(take.audio_path, storage_root, artifact_id)
    except Exception as exc:  # defensive: never let a bad artifact crash the worker loop
        logger.exception("Artifact %s failed", artifact_id)
        _report_artifact(
            client, api_base_url, artifact_id, ArtifactStatus.FAILED, error_message=str(exc)
        )
        return
    _report_artifact(
        client,
        api_base_url,
        artifact_id,
        ArtifactStatus.COMPLETED,
        audio_path=relative_audio_path,
        duration_ms=take.duration_ms,
        voice_profile=voice_profile,
        speedup=take.speedup,
        translated_text=take.text if take.text != message.text else None,
    )


def _report_export(
    client: httpx.Client,
    api_base_url: str,
    export_job_id: str,
    status: JobStatus,
    progress: int | None = None,
    output_path: str | None = None,
    error_message: str | None = None,
) -> None:
    payload = ExportJobCallbackUpdate(
        status=status, progress=progress, output_path=output_path, error_message=error_message
    )
    try:
        response = client.patch(
            f"{api_base_url}/internal/export-jobs/{export_job_id}",
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to report status for export job %s", export_job_id)


def _fetch_segments(client: httpx.Client, api_base_url: str, media_id: str) -> list[Segment]:
    response = client.get(f"{api_base_url}/internal/media/{media_id}/segments")
    response.raise_for_status()
    return [Segment.model_validate(item) for item in response.json()]


def _trimmed_clip(
    abs_path: str, recorded_ms: int | None, tmp_dir: str, index: int
) -> tuple[str, int]:
    """The clip without the silence at its ends, and its length. Falls back to the
    untrimmed clip when trimming fails or leaves (almost) nothing, e.g. a silent mock
    voice."""
    untrimmed = (abs_path, recorded_ms or probe_duration_ms(abs_path))
    trimmed = str(Path(tmp_dir) / f"segment_{index}_trim.wav")
    try:
        trim_silence(abs_path, trimmed)
        trimmed_ms = wav_duration_ms(trimmed)
    except Exception:
        logger.warning("Could not trim silence from %s; using it as is", abs_path, exc_info=True)
        return untrimmed
    if trimmed_ms < MIN_TRIMMED_MS:
        return untrimmed
    return trimmed, trimmed_ms


def _with_background(video_path: str, pieces: list[VideoPiece], dub_wav: str, tmp_dir: str) -> str:
    """The dub over the video's own background sound, when that can be kept; otherwise
    the dub alone. The background follows the same timeline as the picture."""
    background = separate_background(video_path)
    if background is None:
        return dub_wav
    try:
        bed = build_timeline_background(background, pieces, str(Path(tmp_dir) / "bed.wav"))
        original_voice = voice_path(video_path)
        gain = dub_gain_db(dub_wav, str(original_voice)) if original_voice.exists() else 0.0
        return mix_with_background(
            dub_wav, bed, str(Path(tmp_dir) / "soundtrack.wav"), dub_gain_db=gain
        )
    except Exception:  # the dub alone is still a valid export
        logger.warning("Could not mix the background under the dub", exc_info=True)
        return dub_wav


def _timeline_subtitles(segments: list[Segment], starts_and_ends: list[tuple[int, int]]) -> str:
    """SRT for the dubbed lines, timed to the export's timeline (not the source's)."""
    return segments_to_srt(
        [
            TranscriptSegment(
                start_ms=start_ms, end_ms=end_ms, text=segment.translated_text or segment.text
            )
            for segment, (start_ms, end_ms) in zip(segments, starts_and_ends, strict=True)
        ]
    )


def process_export_job(
    client: httpx.Client, api_base_url: str, storage_root: str, message: ExportJobQueueMessage
) -> None:
    export_job_id = str(message.export_job_id)
    _report_export(client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=10)
    try:
        segments = _fetch_segments(client, api_base_url, str(message.media_id))
        video_path = str(Path(storage_root) / message.media_storage_path)
        total_duration_ms = probe_duration_ms(video_path)

        sources: list[tuple[str, int | None, float]] = []
        for segment in segments:
            if segment.artifact is None or segment.artifact.audio_path is None:
                raise RuntimeError(f"segment {segment.id} has no usable audio artifact")
            abs_path = str(Path(storage_root) / segment.artifact.audio_path)
            if not Path(abs_path).exists():
                raise RuntimeError(
                    f"audio file missing on disk for segment {segment.id}: {abs_path}"
                )
            sources.append((abs_path, segment.artifact.duration_ms, segment.artifact.speedup))

        with tempfile.TemporaryDirectory() as tmp_dir:
            clip_paths: list[str] = []
            timings: list[tuple[int, int, int, float]] = []
            for index, (segment, (source, recorded_ms, speedup)) in enumerate(
                zip(segments, sources, strict=True)
            ):
                clip_path, clip_ms = _trimmed_clip(source, recorded_ms, tmp_dir, index)
                clip_paths.append(clip_path)
                timings.append((segment.start_ms, segment.end_ms, clip_ms, speedup))

            # One timeline drives the MP3, the MP4's picture and its subtitles, so they
            # always agree with each other.
            timeline = plan_timeline(timings, total_duration_ms)
            _report_export(client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=30)

            segment_audio: list[tuple[int, str]] = []
            for index, (clip, clip_path) in enumerate(zip(timeline.clips, clip_paths, strict=True)):
                if clip.tempo != 1.0:
                    stretched_path = str(Path(tmp_dir) / f"segment_{index}_tempo.wav")
                    apply_tempo(clip_path, stretched_path, clip.tempo)
                    clip_path = stretched_path
                segment_audio.append((clip.start_ms, clip_path))

            dub_wav = str(Path(tmp_dir) / "dub_track.wav")
            build_dub_audio_track(segment_audio, timeline.duration_ms, dub_wav)
            soundtrack = _with_background(video_path, timeline.pieces, dub_wav, tmp_dir)
            _report_export(client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=50)

            exports_dir = Path(storage_root) / _EXPORTS_SUBDIR
            exports_dir.mkdir(parents=True, exist_ok=True)
            if message.kind == ExportKind.MP3:
                output_path = exports_dir / f"{export_job_id}.mp3"
                encode_mp3(soundtrack, str(output_path))
            else:
                picture = video_path
                if timeline.changes_video:
                    picture = str(Path(tmp_dir) / "timeline_video.mp4")
                    build_timeline_video(video_path, timeline.pieces, tmp_dir, picture)
                _report_export(
                    client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=75
                )
                subtitles = Path(tmp_dir) / "dub.srt"
                subtitles.write_text(
                    _timeline_subtitles(
                        segments,
                        [(clip.start_ms, clip.subtitle_end_ms) for clip in timeline.clips],
                    ),
                    encoding="utf-8",
                )
                output_path = exports_dir / f"{export_job_id}.mp4"
                mux_mp4(
                    picture,
                    soundtrack,
                    str(output_path),
                    subtitles_path=str(subtitles),
                    subtitle_language=_SUBTITLE_LANGUAGE.get(_get_target_lang()),
                )
            _report_export(client, api_base_url, export_job_id, JobStatus.PROCESSING, progress=90)
    except Exception as exc:  # defensive: never let a bad export job crash the worker loop
        logger.exception("Export job %s failed", export_job_id)
        _report_export(
            client, api_base_url, export_job_id, JobStatus.FAILED, error_message=str(exc)
        )
        return

    relative_output = output_path.relative_to(Path(storage_root)).as_posix()
    _report_export(
        client,
        api_base_url,
        export_job_id,
        JobStatus.COMPLETED,
        progress=100,
        output_path=relative_output,
    )


def run() -> None:
    configure_logging()
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    storage_root = os.environ.get("STORAGE_DIR", "/app/data")

    # socket_timeout must exceed BLPOP's block timeout below, or redis-py's
    # client-side read timeout races the server-side block and raises
    # spurious TimeoutErrors on every idle poll.
    r = redis.from_url(redis_url, decode_responses=True, socket_timeout=10)
    logger.info(
        "DubForge worker started; listening on %s, %s, %s",
        JOB_QUEUE_KEY,
        ARTIFACT_QUEUE_KEY,
        EXPORT_QUEUE_KEY,
    )

    with httpx.Client(timeout=30.0) as client:
        while True:
            try:
                item = r.blpop([JOB_QUEUE_KEY, ARTIFACT_QUEUE_KEY, EXPORT_QUEUE_KEY], timeout=5)
            except redis.RedisError:
                logger.exception("Redis connection error; retrying")
                continue
            if item is None:
                continue
            key, raw = item
            if key == JOB_QUEUE_KEY:
                try:
                    job_message = JobQueueMessage.model_validate_json(raw)
                except Exception:
                    logger.exception("Dropping malformed job message: %s", raw)
                    continue
                process_job(client, api_base_url, storage_root, job_message)
            elif key == ARTIFACT_QUEUE_KEY:
                try:
                    artifact_message = ArtifactQueueMessage.model_validate_json(raw)
                except Exception:
                    logger.exception("Dropping malformed artifact message: %s", raw)
                    continue
                process_artifact(client, api_base_url, storage_root, artifact_message)
            else:
                try:
                    export_message = ExportJobQueueMessage.model_validate_json(raw)
                except Exception:
                    logger.exception("Dropping malformed export job message: %s", raw)
                    continue
                process_export_job(client, api_base_url, storage_root, export_message)


if __name__ == "__main__":
    run()
