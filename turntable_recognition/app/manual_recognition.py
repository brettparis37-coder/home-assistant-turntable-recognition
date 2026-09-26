"""One explicit command captures one bounded USB sample and requests one match."""
import json
import sys
import tempfile
import threading
import wave


class ManualRecognition:
    def __init__(self, options, publisher, limiter, provider_factory):
        self.options = options
        self.publisher = publisher
        self.limiter = limiter
        self.provider_factory = provider_factory
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.busy = False
        self.recording = False
        self.data = bytearray()
        self.error = ""
        self.target = int(options.get("sample_seconds", 10)) * 16000 * 2 * 2

    def start(self):
        day, month = self.limiter.counts()
        self.publisher.publish_status("ready", day, month)
        threading.Thread(target=self.listen, daemon=True).start()

    def listen(self):
        for line in sys.stdin:
            try:
                command = json.loads(line)
                if isinstance(command, dict) and command.get("command") == "recognize":
                    self.request()
                else:
                    print("Ignored unknown input command", flush=True)
            except (ValueError, TypeError):
                print("Ignored invalid input command", flush=True)

    def request(self):
        with self.lock:
            if self.busy:
                print("Recognition already active; duplicate command ignored", flush=True)
                return False
            self.busy = True
            self.recording = True
            self.data.clear()
            self.error = ""
            self.ready.clear()
        threading.Thread(target=self.recognize, daemon=True).start()
        return True

    def feed(self, pcm):
        with self.lock:
            if self.recording:
                remaining = self.target - len(self.data)
                self.data.extend(pcm[:remaining])
                if len(self.data) == self.target:
                    self.recording = False
                    self.ready.set()

    def disconnect(self):
        with self.lock:
            if self.recording:
                self.error = "USB capture disconnected during sampling"
                self.recording = False
                self.ready.set()

    def recognize(self):
        try:
            day, month = self.limiter.counts()
            self.publisher.publish_status("capturing", day, month)
            if not self.ready.wait(int(self.options.get("sample_seconds", 10)) + 30):
                raise RuntimeError("Timed out waiting for live USB audio")
            with self.lock:
                if self.error:
                    raise RuntimeError(self.error)
                pcm = bytes(self.data)
                self.data.clear()
            provider = self.provider_factory(str(self.options.get("audd_api_token", "")))
            with tempfile.TemporaryDirectory(prefix="turntable-") as directory:
                path = directory + "/sample.wav"
                with wave.open(path, "wb") as output:
                    output.setnchannels(2)
                    output.setsampwidth(2)
                    output.setframerate(16000)
                    output.writeframes(pcm)
                day, month = self.limiter.consume()
                self.publisher.publish_status("recognizing", day, month)
                track = provider.recognize(path, False)
                self.publisher.publish_track(track, "recognized", day, month)
                print(f"Live USB recognized: {track.artist} - {track.title}", flush=True)
        except Exception as exc:
            print(f"Manual recognition error: {exc}", file=sys.stderr, flush=True)
            try:
                day, month = self.limiter.counts()
                self.publisher.publish_status("error", day, month, str(exc))
            except Exception as publish_error:
                print(f"Could not publish recognition error: {publish_error}", file=sys.stderr, flush=True)
        finally:
            with self.lock:
                self.busy = False
                self.recording = False
                self.data.clear()
