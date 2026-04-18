"""Audio player using sounddevice + soundfile.

Supports FLAC, WAV, AIFF and any format libsndfile can read.
Allows selecting the output device (WASAPI, DirectSound, etc.).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

import sounddevice as sd
import soundfile as sf
import numpy as np

from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class AudioPlayer(QObject):
    """Thread-based audio player with play/pause/stop and position tracking."""

    position_changed = pyqtSignal(float)    # elapsed seconds
    state_changed = pyqtSignal(str)         # "playing" | "paused" | "stopped"
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._path: Path | None = None
        self._device: int | None = None     # None = system default
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()             # not paused initially
        self._elapsed = 0.0
        self._duration = 0.0
        self._samplerate = 0
        self._lock = threading.Lock()

        # Position timer — fires in main thread
        self._pos_timer = QTimer(self)
        self._pos_timer.setInterval(200)
        self._pos_timer.timeout.connect(self._emit_position)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: Path | str) -> bool:
        self.stop()
        self._path = Path(path)
        try:
            info = sf.info(self._path)
            self._duration = info.duration
            self._samplerate = info.samplerate
            return True
        except Exception as e:
            self.error.emit(str(e))
            return False

    def play(self, seek: float = 0.0) -> None:
        if not self._path:
            return
        self.stop()
        self._elapsed = seek
        self._stop_event.clear()
        self._pause_event.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._pos_timer.start()
        self.state_changed.emit("playing")

    def pause(self) -> None:
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.state_changed.emit("paused")
        else:
            self._pause_event.set()
            self.state_changed.emit("playing")

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()     # unblock if paused
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._pos_timer.stop()
        self._elapsed = 0.0
        self.state_changed.emit("stopped")

    def seek(self, seconds: float) -> None:
        if self._path:
            self.play(seek=seconds)

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and self._pause_event.is_set()

    def set_device(self, device_id: int | None) -> None:
        self._device = device_id

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            with sf.SoundFile(self._path) as f:
                # Seek to start position
                if self._elapsed > 0:
                    frame_start = int(self._elapsed * f.samplerate)
                    f.seek(min(frame_start, f.frames - 1))

                block_size = 4096
                stream_kwargs = dict(
                    samplerate=f.samplerate,
                    channels=f.channels,
                    dtype="float32",
                    device=self._device,
                )
                with sd.OutputStream(**stream_kwargs) as stream:
                    for block in f.blocks(blocksize=block_size, dtype="float32"):
                        if self._stop_event.is_set():
                            break
                        # Pause: wait until unpaused
                        self._pause_event.wait()
                        if self._stop_event.is_set():
                            break
                        stream.write(block)
                        with self._lock:
                            self._elapsed += len(block) / f.samplerate

        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._pos_timer.stop()
            if not self._stop_event.is_set():
                self._elapsed = 0.0
                self.finished.emit()
                self.state_changed.emit("stopped")

    def _emit_position(self) -> None:
        self.position_changed.emit(self._elapsed)


# ------------------------------------------------------------------
# Device enumeration
# ------------------------------------------------------------------

def list_output_devices() -> list[dict]:
    """Return list of dicts with 'id', 'name', 'hostapi_name'."""
    devices = []
    try:
        all_devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        for i, dev in enumerate(all_devices):
            if dev["max_output_channels"] > 0:
                hostapi_name = hostapis[dev["hostapi"]]["name"] if dev["hostapi"] < len(hostapis) else ""
                devices.append({
                    "id": i,
                    "name": dev["name"],
                    "hostapi_name": hostapi_name,
                    "display": f"{dev['name']} [{hostapi_name}]",
                    "default": (i == sd.default.device[1]),
                })
    except Exception:
        pass
    return devices


def get_default_device_id() -> int | None:
    try:
        default = sd.default.device
        return default[1] if default[1] >= 0 else None
    except Exception:
        return None
