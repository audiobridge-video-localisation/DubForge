from abc import ABC, abstractmethod

from dubforge_contracts.models import AudioResult, SpeakerSegment, TranscriptSegment


class STTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> list[TranscriptSegment]: ...


class DiarizationProvider(ABC):
    @abstractmethod
    def diarize(self, audio_path: str) -> list[SpeakerSegment]: ...


class TranslationProvider(ABC):
    @abstractmethod
    def translate(
        self, text: str, src_lang: str, tgt_lang: str, context: list[str] | None = None
    ) -> str: ...

    def translate_candidates(
        self, text: str, src_lang: str, tgt_lang: str, count: int = 1
    ) -> list[str]:
        """Up to `count` alternative translations, best first.

        Providers that cannot offer alternatives return just their one translation. The
        caller may pick a later alternative when the first is too long to be spoken in time.
        """
        return [self.translate(text, src_lang, tgt_lang)]


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_profile: str,
        target_duration_ms: int | None = None,
        speaker_index: int | None = None,
        voice_gender: str | None = None,
    ) -> AudioResult:
        """speaker_index distinguishes diarized speakers in the same media (e.g. picking a
        different voice from a per-language pool). voice_gender ("male"/"female") steers
        which gender the dominant/first speaker (speaker_index 0) gets. Providers that only
        support one voice per language (mock, MMS) accept and ignore both."""
