import os
import tempfile
import wave

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
        audio_path = self._write_silent_wav(actual_duration_ms)
        return AudioResult(audio_path=audio_path, actual_duration_ms=actual_duration_ms)

    @staticmethod
    def _write_silent_wav(duration_ms: int, sample_rate: int = 16000) -> str:
        # Real providers write real bytes; the mock used to just fabricate a
        # path that was never created, which made downstream code (artifact
        # persistence, export assembly) silently operate on a nonexistent
        # file. Writing an actual silent WAV keeps the mock provider a
        # faithful stand-in for the real ones.
        num_samples = int(sample_rate * duration_ms / 1000)
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * num_samples)
        return path
