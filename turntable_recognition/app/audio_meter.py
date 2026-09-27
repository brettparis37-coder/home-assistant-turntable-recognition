"""Local USB signal meter using Home Assistant's shared PulseAudio server."""

from array import array
import json
import math
import os
import select
import subprocess
import sys
import tempfile
import time

from diagnostics import exception_details, log_event


def levels(pcm: bytes) -> tuple[float, float]:
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise ValueError("No audio samples received")
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768
    peak = max(abs(value) for value in samples) / 32768
    return tuple(round(max(-100.0, 20 * math.log10(max(value, 0.00001))), 1)
                 for value in (rms, peak))


def select_source(configured: str) -> str:
    result = subprocess.run(
        ["pactl", "--format=json", "list", "sources"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    sources = json.loads(result.stdout)
    available = [item["name"] for item in sources if not item["name"].endswith(".monitor")]
    log_event("recording_inputs_discovered", available_inputs=available,
              configured_source=configured)
    if configured != "auto":
        if configured not in available:
            raise RuntimeError(f"Configured audio source is missing: {configured}")
        return configured
    matches = []
    for source in sources:
        properties = source.get("properties") or {}
        identity = (source["name"] + " " + json.dumps(properties)).lower()
        if source["name"].endswith(".monitor"):
            continue
        if "usb" in identity and ("burr-brown" in identity or "08bb" in identity
                                  or "usb_audio_codec" in identity):
            matches.append(source["name"])
    if len(matches) != 1:
        raise RuntimeError("Expected one UFO202 USB Audio CODEC input; found "
                           f"{len(matches)}. Check USB connection or set audio_source explicitly.")
    return matches[0]


def read_window(process, count: int, timeout: float = 10) -> bytes:
    data = bytearray()
    deadline = time.monotonic() + timeout
    while len(data) < count:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
            raise RuntimeError("USB audio input stopped delivering samples")
        chunk = os.read(process.stdout.fileno(), count - len(data))
        if not chunk:
            raise RuntimeError("Audio capture process stopped")
        data.extend(chunk)
    return bytes(data)


def stop_process(process) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    process.stdout.close()


def run_meter(options: dict, publisher, manual=None, automatic=None) -> None:
    threshold = float(options.get("audio_threshold_dbfs", -50))
    configured = str(options.get("audio_source", "auto"))
    interval = int(options.get("audio_update_seconds", 1))
    base_attributes = {
        "unit_of_measurement": "dB", "state_class": "measurement",
        "icon": "mdi:waveform", "measurement_reference": "dBFS",
    }
    while True:
        process = None
        try:
            source = select_source(configured)
            log_event("audio_monitor_started", source=source,
                      mode="automatic" if automatic else "manual",
                      sample_rate_hz=16000, channels=2, update_seconds=interval,
                      signal_threshold_dbfs=threshold)
            with tempfile.TemporaryFile() as errors:
                process = subprocess.Popen([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                    "-f", "pulse", "-i", source, "-ac", "2", "-ar", "16000",
                    "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
                ], stdout=subprocess.PIPE, stderr=errors, bufsize=0)
                try:
                    while True:
                        pcm = read_window(process, 16000 * 2 * 2 * interval,
                                          max(10, interval + 5))
                        if manual is not None:
                            manual.feed(pcm)
                        rms, peak = levels(pcm)
                        if automatic is not None:
                            automatic.feed(pcm, rms)
                        publisher.set_state("audio_level", str(rms), {
                            **base_attributes, "friendly_name": "Turntable Audio Level",
                            "audio_source": source,
                        })
                        publisher.set_state("audio_peak", str(peak), {
                            **base_attributes, "friendly_name": "Turntable Audio Peak",
                        })
                        publisher.set_state("audio_signal", "audio" if rms >= threshold else "quiet", {
                            "friendly_name": "Turntable Audio Signal", "icon": "mdi:music",
                            "threshold_dbfs": threshold,
                        })
                        publisher.set_state("audio_input_status", "monitoring", {
                            "friendly_name": "Turntable Audio Input Status",
                            "audio_source": source, "last_error": "",
                        })
                except Exception as exc:
                    stop_process(process)
                    process = None
                    errors.seek(0)
                    detail = errors.read().decode("utf-8", errors="replace").strip()[-1000:]
                    raise RuntimeError(f"{exc}{': ' + detail if detail else ''}") from exc
        except Exception as exc:
            if automatic is not None:
                automatic.disconnect()
            if manual is not None:
                manual.disconnect()
            if process is not None:
                stop_process(process)
            message = str(exc)
            log_event("audio_monitor_failed", level="ERROR", retry_in_seconds=5,
                      **exception_details(exc))
            try:
                for suffix, name in (("audio_level", "Turntable Audio Level"),
                                     ("audio_peak", "Turntable Audio Peak"),
                                     ("audio_signal", "Turntable Audio Signal")):
                    publisher.set_state(suffix, "unavailable", {"friendly_name": name})
                publisher.set_state("audio_input_status", "error", {
                    "friendly_name": "Turntable Audio Input Status", "last_error": message,
                })
            except Exception as publish_error:
                log_event("audio_monitor_error_state_publish_failed", level="ERROR",
                          **exception_details(publish_error))
            time.sleep(5)

