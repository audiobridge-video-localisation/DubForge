from datetime import UTC, datetime

from dubforge_contracts.models import (
    Artifact,
    ArtifactStatus,
    SegmentAudioStatus,
    compute_audio_status,
    segment_room_ms,
)

NOW = datetime.now(UTC)


def _artifact(
    status: ArtifactStatus, duration_ms: int | None = None, speedup: float = 1.0
) -> Artifact:
    return Artifact(
        status=status, duration_ms=duration_ms, speedup=speedup, created_at=NOW, updated_at=NOW
    )


def test_no_artifact_is_no_audio() -> None:
    assert compute_audio_status(1000, None) == SegmentAudioStatus.NO_AUDIO


def test_pending_or_processing_artifact_is_pending() -> None:
    assert (
        compute_audio_status(1000, _artifact(ArtifactStatus.PENDING)) == SegmentAudioStatus.PENDING
    )
    assert (
        compute_audio_status(1000, _artifact(ArtifactStatus.PROCESSING))
        == SegmentAudioStatus.PENDING
    )


def test_failed_artifact_is_failed() -> None:
    assert compute_audio_status(1000, _artifact(ArtifactStatus.FAILED)) == SegmentAudioStatus.FAILED


def test_outdated_artifact_is_outdated() -> None:
    assert (
        compute_audio_status(1000, _artifact(ArtifactStatus.OUTDATED))
        == SegmentAudioStatus.OUTDATED
    )


def test_completed_with_missing_duration_is_mismatch() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=None)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.MISMATCH


def test_completed_within_what_export_can_speed_up_is_ready() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=1250)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.READY


def test_completed_just_over_what_speech_alone_can_fit_is_stretched() -> None:
    # past what faster speech covers, but the export can slow the video to make room
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=1251)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.STRETCHED


def test_completed_past_what_the_export_can_absorb_is_mismatch() -> None:
    # 1.25x faster speech over 1.25x slower video covers 1562.5ms of a 1000ms room
    assert (
        compute_audio_status(1000, _artifact(ArtifactStatus.COMPLETED, duration_ms=1562))
        == SegmentAudioStatus.STRETCHED
    )
    assert (
        compute_audio_status(1000, _artifact(ArtifactStatus.COMPLETED, duration_ms=1563))
        == SegmentAudioStatus.MISMATCH
    )


def test_short_line_gets_no_fixed_floor_export_cannot_honour() -> None:
    # 700 ms in a 400 ms slot needs 1.75x; export stops at 1.25x.
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=700)
    assert compute_audio_status(400, artifact) == SegmentAudioStatus.MISMATCH


def test_speed_up_already_spent_by_the_voice_is_not_counted_twice() -> None:
    # the voice used all of the 1.25x, so only the slower video is left for export
    sped_up = _artifact(ArtifactStatus.COMPLETED, duration_ms=1100, speedup=1.25)
    assert compute_audio_status(1000, sped_up) == SegmentAudioStatus.STRETCHED
    too_long = _artifact(ArtifactStatus.COMPLETED, duration_ms=1251, speedup=1.25)
    assert compute_audio_status(1000, too_long) == SegmentAudioStatus.MISMATCH
    fits = _artifact(ArtifactStatus.COMPLETED, duration_ms=1000, speedup=1.25)
    assert compute_audio_status(1000, fits) == SegmentAudioStatus.READY


def test_completed_shorter_than_slot_is_ready() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=250)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.READY


def test_completed_under_a_quarter_of_the_slot_is_mismatch() -> None:
    # more likely a clipped or silent take than a terse translation
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=249)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.MISMATCH


def test_completed_zero_length_is_failed() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=0)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.FAILED


def test_completed_just_under_rel_tolerance_is_ready_for_long_segment() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=12500)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.READY


def test_completed_just_over_rel_tolerance_is_stretched_for_long_segment() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=12501)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.STRETCHED
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=15626)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.MISMATCH


def test_completed_shorter_than_long_segment_is_ready() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=3000)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.READY


def test_dub_may_use_the_silence_before_the_next_line() -> None:
    # slot 1000, but the next line starts at 2500: room 2500, tolerance 625
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=3000)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.MISMATCH
    assert compute_audio_status(1000, artifact, room_ms=2500) == SegmentAudioStatus.READY


def test_dub_longer_than_its_room_plus_tolerance_is_stretched_then_a_mismatch() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=3200)
    assert compute_audio_status(1000, artifact, room_ms=2500) == SegmentAudioStatus.STRETCHED
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=4000)
    assert compute_audio_status(1000, artifact, room_ms=2500) == SegmentAudioStatus.MISMATCH


def test_a_room_smaller_than_the_slot_never_tightens_the_rule() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=1250)
    assert compute_audio_status(1000, artifact, room_ms=400) == SegmentAudioStatus.READY


def test_segment_room_runs_to_the_next_line_and_the_last_line_has_only_its_slot() -> None:
    assert segment_room_ms(1000, 1500, 4000) == 3000
    assert segment_room_ms(1000, 1500, 2000) == 1500  # overlapping/adjacent: never below the slot
    assert segment_room_ms(1000, 1500, None) == 1500
