import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import requests

log = logging.getLogger("leadback.stt")

STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg"}
CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
}
MAX_AUDIO_BYTES = 50 * 1024 * 1024
DEFAULT_TIMEOUT = 120
MAX_ATTEMPTS = 3

RETRY_STATUS = {429, 500, 502, 503, 504}


class STTError(Exception):
    pass


@dataclass
class TranscriptWord:
    text: str
    start: float | None
    end: float | None
    speaker_id: str | None
    type: str


@dataclass
class Transcript:
    text: str
    words: list
    language_code: str | None
    duration_secs: float | None
    provider: str


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes, filename: str) -> Transcript: ...


def is_audio_filename(filename):
    if not filename:
        return False
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _content_type(filename):
    return CONTENT_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


def _backoff(attempt):
    time.sleep(min(2**attempt, 16))


def _from_elevenlabs(payload):
    words = []
    for w in payload.get("words") or []:
        words.append(
            TranscriptWord(
                text=w.get("text") or "",
                start=w.get("start"),
                end=w.get("end"),
                speaker_id=w.get("speaker_id"),
                type=w.get("type") or "word",
            )
        )
    return Transcript(
        text=payload.get("text") or "",
        words=words,
        language_code=payload.get("language_code"),
        duration_secs=payload.get("audio_duration_secs"),
        provider="elevenlabs",
    )


class ElevenLabsScribe:
    def __init__(self, api_key=None, timeout=None):
        self.api_key = (
            api_key if api_key is not None else os.getenv("ELEVENLABS_API_KEY", "")
        )
        self.timeout = (
            timeout
            if timeout is not None
            else int(os.getenv("ELEVENLABS_TIMEOUT", DEFAULT_TIMEOUT))
        )

    def transcribe(self, audio: bytes, filename: str) -> Transcript:
        if not self.api_key:
            raise STTError("ELEVENLABS_API_KEY is not set")
        if not is_audio_filename(filename):
            raise STTError("unsupported type, use wav/mp3/m4a/ogg")
        if not audio:
            raise STTError("empty file")
        if len(audio) > MAX_AUDIO_BYTES:
            raise STTError("file too large")

        log.info("stt.start provider=elevenlabs file=%s bytes=%s", filename, len(audio))

        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                resp = requests.post(
                    STT_URL,
                    headers={"xi-api-key": self.api_key},
                    files={"file": (filename, audio, _content_type(filename))},
                    data={
                        "model_id": "scribe_v2",
                        "diarize": "true",
                        "timestamps_granularity": "word",
                        "tag_audio_events": "true",
                    },
                    timeout=self.timeout,
                )
            except requests.Timeout:
                last_error = STTError(f"stt timeout after {self.timeout}s")
                log.info("stt.retry attempt=%s reason=timeout", attempt)
                if attempt < MAX_ATTEMPTS:
                    _backoff(attempt)
                continue
            except requests.RequestException as e:
                last_error = STTError(f"stt request failed: {e}")
                log.info("stt.retry attempt=%s reason=%s", attempt, e)
                if attempt < MAX_ATTEMPTS:
                    _backoff(attempt)
                continue

            if resp.status_code in RETRY_STATUS:
                last_error = STTError(f"stt http {resp.status_code}: {resp.text[:200]}")
                log.info("stt.retry attempt=%s status=%s", attempt, resp.status_code)
                if attempt < MAX_ATTEMPTS:
                    _backoff(attempt)
                continue

            if resp.status_code >= 400:
                log.info(
                    "stt.fail status=%s body=%s", resp.status_code, resp.text[:200]
                )
                raise STTError(f"stt http {resp.status_code}: {resp.text[:200]}")

            try:
                payload = resp.json()
            except ValueError:
                log.info("stt.fail reason=invalid_json")
                raise STTError("stt returned invalid json")

            transcript = _from_elevenlabs(payload)
            log.info(
                "stt.ok words=%s duration=%s",
                len(transcript.words),
                transcript.duration_secs,
            )
            return transcript

        log.info("stt.fail after %s attempts: %s", MAX_ATTEMPTS, last_error)
        raise last_error or STTError("stt failed")


def first_speaker_id(transcript):
    for word in transcript.words or []:
        if word.speaker_id:
            return word.speaker_id
    return None


def get_stt() -> SpeechToText:
    provider = os.getenv("STT_PROVIDER", "elevenlabs")
    if provider == "elevenlabs":
        return ElevenLabsScribe()
    raise STTError(f"unknown STT provider: {provider}")
