import time
from typing import Any

import httpx

from dubforge_contracts.models import SpeakerSegment, TranscriptSegment

UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"


def _run_transcription(
    client: httpx.Client,
    audio_path: str,
    api_key: str,
    poll_interval_s: float,
    timeout_s: float,
) -> list[dict[str, Any]]:
    headers = {"authorization": api_key}

    with open(audio_path, "rb") as audio_file:
        upload_response = client.post(UPLOAD_URL, headers=headers, content=audio_file)
    upload_response.raise_for_status()
    upload_url = upload_response.json()["upload_url"]

    submit_response = client.post(
        TRANSCRIPT_URL,
        headers=headers,
        json={"audio_url": upload_url, "speaker_labels": True},
    )
    submit_response.raise_for_status()
    transcript_id = submit_response.json()["id"]

    deadline = time.monotonic() + timeout_s
    while True:
        poll_response = client.get(f"{TRANSCRIPT_URL}/{transcript_id}", headers=headers)
        poll_response.raise_for_status()
        result = poll_response.json()
        status = result["status"]

        if status == "completed":
            return list(result.get("utterances") or [])
        if status == "error":
            raise RuntimeError(f"AssemblyAI transcription failed: {result.get('error')}")
        if time.monotonic() > deadline:
            raise RuntimeError(f"AssemblyAI transcription timed out after {timeout_s}s")
        time.sleep(poll_interval_s)


def transcribe_with_diarization(
    audio_path: str,
    api_key: str,
    poll_interval_s: float = 3.0,
    timeout_s: float = 600.0,
    client: httpx.Client | None = None,
) -> tuple[list[TranscriptSegment], list[SpeakerSegment]]:
    """Transcribe and diarize an audio file via AssemblyAI's pre-recorded API.

    Returns parallel (same order/length) TranscriptSegment and SpeakerSegment
    lists, one pair per speaker-labeled utterance. `client` is injectable for
    testing; a dedicated client is created and closed when omitted.
    """
    if client is not None:
        utterances = _run_transcription(client, audio_path, api_key, poll_interval_s, timeout_s)
    else:
        with httpx.Client(timeout=120.0) as owned_client:
            utterances = _run_transcription(
                owned_client, audio_path, api_key, poll_interval_s, timeout_s
            )
    transcripts = [
        TranscriptSegment(start_ms=u["start"], end_ms=u["end"], text=u["text"]) for u in utterances
    ]
    speakers = [
        SpeakerSegment(
            start_ms=u["start"], end_ms=u["end"], speaker_label=f"Speaker {u['speaker']}"
        )
        for u in utterances
    ]
    return transcripts, speakers
