from datetime import UTC, datetime

from dubforge_contracts.models import (
    Artifact,
    ArtifactStatus,
    SegmentAudioStatus,
    compute_audio_status,
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


def test_completed_just_over_abs_tolerance_is_mismatch() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=1301)
    assert compute_audio_status(1000, artifact) == SegmentAudioStatus.MISMATCH


def test_completed_just_under_rel_tolerance_is_ready_for_long_segment() -> None:
    # 10000ms expected, tolerance is max(300, 1500) = 1500ms.
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=11500)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.READY


def test_completed_just_over_rel_tolerance_is_mismatch_for_long_segment() -> None:
    artifact = _artifact(ArtifactStatus.COMPLETED, duration_ms=11501)
    assert compute_audio_status(10000, artifact) == SegmentAudioStatus.MISMATCH
