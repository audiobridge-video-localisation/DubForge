from abc import ABC, abstractmethod

from dubforge_contracts.models import AudioResult, SpeakerSegment, TranscriptSegment


class STTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        ...


class DiarizationProvider(ABC):
    @abstractmethod
    def diarize(self, audio_path: str) -> list[SpeakerSegment]:
        ...


class TranslationProvider(ABC):
    @abstractmethod
    def translate(
        self, text: str, src_lang: str, tgt_lang: str, context: list[str] | None = None
    ) -> str:
        ...


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        ...