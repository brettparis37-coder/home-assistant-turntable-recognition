"""Small rolling archive of failed live-recognition audio samples."""

from __future__ import annotations

import json
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FailedSampleArchive:
    def __init__(self, directory: str | Path = "/media/turntable_recognition/failed_samples",
                 keep: int = 5) -> None:
        self.directory = Path(directory)
        self.keep = max(0, min(20, int(keep)))

    def save(self, pcm: bytes, attempt_id: int, error: str,
             capture_stats: dict[str, Any] | None = None) -> dict[str, str] | None:
        """Persist a submitted-but-failed 16 kHz stereo s16le sample, then evict old files."""
        if self.keep == 0:
            return None
        self.directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc)
        stamp = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
        kind = "no-match" if "No song was recognized" in error else "error"
        stem = f"failed_{stamp}_attempt-{attempt_id:04d}_{kind}"
        wav_path = self.directory / f"{stem}.wav"
        metadata_path = self.directory / f"{stem}.json"
        wav_tmp = self.directory / f".{stem}.wav.tmp"
        metadata_tmp = self.directory / f".{stem}.json.tmp"
        try:
            with wave.open(str(wav_tmp), "wb") as output:
                output.setnchannels(2)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(pcm)
            metadata = {
                "captured_at": timestamp.isoformat(),
                "attempt_id": attempt_id,
                "outcome": kind,
                "error": error[:1000],
                "sample_seconds": round(len(pcm) / 64000, 3),
                "sample_bytes": len(pcm),
                "format": "WAV, 16 kHz, stereo, signed 16-bit PCM",
                "levels": capture_stats or {},
            }
            metadata_tmp.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            wav_tmp.replace(wav_path)
            metadata_tmp.replace(metadata_path)
        finally:
            wav_tmp.unlink(missing_ok=True)
            metadata_tmp.unlink(missing_ok=True)

        samples = sorted(self.directory.glob("failed_*.wav"), key=lambda item: item.stat().st_mtime_ns)
        for stale in samples[:-self.keep]:
            stale.unlink(missing_ok=True)
            stale.with_suffix(".json").unlink(missing_ok=True)
        return {
            "filename": wav_path.name,
            "path": str(wav_path),
            "media_content_id": "media-source://media_source/local/turntable_recognition/failed_samples/" + wav_path.name,
        }


