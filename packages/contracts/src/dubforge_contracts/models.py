from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None


class SpeakerSegment(BaseModel):
    start_ms: int
    end_ms: int
    speaker_label: str


class AudioResult(BaseModel):
    audio_path: str
    actual_duration_ms: int