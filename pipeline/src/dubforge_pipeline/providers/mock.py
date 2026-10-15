from dubforge_contracts.models import AudioResult, SpeakerSegment, TranscriptSegment

from .base import DiarizationProvider, STTProvider, TranslationProvider, TTSProvider


class MockSTTProvider(STTProvider):
    def transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(start_ms=0, end_ms=2000, text="Hello, this is a test."),
            TranscriptSegment(start_ms=2000, end_ms=4500, text="This is the second line."),
        ]


class MockDiarizationProvider(DiarizationProvider):
    def diarize(self, audio_path: str) -> list[SpeakerSegment]:
        return [
            SpeakerSegment(start_ms=0, end_ms=2000, speaker_label="Speaker_0"),
            SpeakerSegment(start_ms=2000, end_ms=4500, speaker_label="Speaker_1"),
        ]


class MockTranslationProvider(TranslationProvider):
    def translate(
        self, text: str, src_lang: str, tgt_lang: str, context: list[str] | None = None
    ) -> str:
        return f"[{tgt_lang}] {text}"


class MockTTSProvider(TTSProvider):
    def synthesize(
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        actual_duration_ms = target_duration_ms if target_duration_ms is not None else 2000
        return AudioResult(audio_path="/tmp/mock_audio.wav", actual_duration_ms=actual_duration_ms)
