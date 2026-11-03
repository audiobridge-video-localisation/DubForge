from datetime import UTC, datetime

from dubforge_contracts.models import (
    Artifact,
    ArtifactStatus,
    SegmentAudioStatus,
    compute_audio_status,
    segment_room_ms,
)

NOW = datetime.now(UTC)


def _artifact(status: ArtifactStatus, duration_ms: int | None = None) -> Artifact:
    return Artifact(status=status, duration_ms=duration_ms, created_at=NOW, updated_at=NOW)


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


def test_completed_within_tolerance_is_ready() -> None:
    # 1000ms expected, tolerance is max(300, 150) = 300ms.
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=1250)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.READY


def test_completed_exactly_at_abs_tolerance_is_ready() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=1300)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.READY


def test_completed_just_over_abs_tolerance_is_mismatch() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=1301)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.MISMATCH


def test_completed_much_shorter_than_slot_is_ready() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=200)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.READY


def test_completed_zero_length_is_ready() -> None:
    # Shorter audio is never a mismatch, even degenerate durations.
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=0)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.READY


def test_completed_just_under_rel_tolerance_is_ready_for_long_segment() -> None:
    # 10000ms expected, tolerance is max(300, 2500) = 2500ms.
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=12500)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.READY


def test_completed_just_over_rel_tolerance_is_mismatch_for_long_segment() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=12501)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.MISMATCH


def test_completed_much_shorter_than_long_segment_is_ready() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=2000)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.READY


def test_dub_may_use_the_silence_before_the_next_line() -> None:
    # slot 1000, but the next line starts at 2500: room 2500, tolerance 625
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=3000)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.MISMATCH
    assert compute_audio_status(1000, artifact, room_ms=2500) == SegmentAudioStatus.READY


def test_dub_longer_than_its_room_plus_tolerance_is_still_a_mismatch() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=3200)
    assert compute_audio_status(1000, artifact, room_ms=2500) == SegmentAudioStatus.MISMATCH


def test_a_room_smaller_than_the_slot_never_tightens_the_rule() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=1250)
    assert compute_audio_status(1000, artifact, room_ms=400) == SegmentAudioStatus.READY


def test_segment_room_runs_to_the_next_line_and_the_last_line_has_only_its_slot() -> None:
    assert segment_room_ms(1000, 1500, 4000) == 3000
    assert segment_room_ms(1000, 1500, 2000) == 1500  # overlapping/adjacent: never below the slot
    assert segment_room_ms(1000, 1500, None) == 1500
