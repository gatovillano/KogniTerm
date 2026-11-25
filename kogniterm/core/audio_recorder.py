"""
Grabador de audio multiplataforma desde el micrófono para dictado por voz en la TUI.

Utiliza herramientas del sistema disponibles (pw-record, parecord, arecord, rec/sox, ffmpeg)
con fallback opcional a `sounddevice` si está instalado, grabando en WAV PCM 16kHz mono
(formato óptimo para faster-whisper).
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import wave
from typing import List, Optional, Tuple

logger = logging.getLogger("kogniterm.core.audio_recorder")


class AudioRecorderError(RuntimeError):
    """Error al inicializar o capturar audio desde el micrófono."""


class AudioRecorder:
    """Captura audio del micrófono en formato WAV 16kHz mono 16-bit."""

    SAMPLE_RATE = 16000
    CHANNELS = 1

    def __init__(self, backend: Optional[str] = None):
        self._preferred_backend = backend
        self._backend: Optional[str] = None
        self._process: Optional[subprocess.Popen] = None
        self._temp_file: Optional[str] = None
        self._start_time: Optional[float] = None
        self._is_recording: bool = False

        # Campos usados solo cuando el backend es sounddevice
        self._sd_stream = None
        self._sd_frames: List[bytes] = []
        self._sd_lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def backend_name(self) -> Optional[str]:
        return self._backend

    @property
    def elapsed_seconds(self) -> float:
        if not self._is_recording or self._start_time is None:
            return 0.0
        return max(0.0, time.monotonic() - self._start_time)

    @classmethod
    def detect_backend(cls) -> Optional[str]:
        """Detecta el mejor backend disponible para grabar desde micrófono."""
        system = platform.system().lower()
        if system == "linux":
            candidates = ["pw-record", "parecord", "arecord", "rec", "ffmpeg"]
        elif system == "darwin":
            candidates = ["rec", "ffmpeg"]
        else:
            candidates = ["ffmpeg"]

        for tool in candidates:
            if shutil.which(tool):
                return tool

        try:
            import sounddevice  # noqa: F401
            return "sounddevice"
        except Exception:
            return None

    def _build_cli_command(self, backend: str, output_path: str) -> List[str]:
        """Construye el comando CLI para grabar WAV PCM s16le 16kHz mono."""
        sr = str(self.SAMPLE_RATE)
        ch = str(self.CHANNELS)

        if backend == "pw-record":
            return [
                "pw-record",
                "--format", "s16",
                "--rate", sr,
                "--channels", ch,
                output_path,
            ]
        if backend == "parecord":
            return [
                "parecord",
                "--file-format=wav",
                "--format=s16le",
                f"--rate={sr}",
                f"--channels={ch}",
                output_path,
            ]
        if backend == "arecord":
            return [
                "arecord",
                "-q",
                "-f", "S16_LE",
                "-r", sr,
                "-c", ch,
                "-t", "wav",
                output_path,
            ]
        if backend == "rec":
            return [
                "rec",
                "-q",
                "-r", sr,
                "-c", ch,
                "-b", "16",
                "-e", "signed-integer",
                output_path,
            ]
        if backend == "ffmpeg":
            system = platform.system().lower()
            if system == "darwin":
                in_args = ["-f", "avfoundation", "-i", ":0"]
            elif system == "windows":
                in_args = ["-f", "dshow", "-i", "audio=default"]
            else:
                in_args = ["-f", "pulse", "-i", "default"]
            return [
                "ffmpeg",
                "-y",
                "-loglevel", "error",
                *in_args,
                "-ar", sr,
                "-ac", ch,
                "-c:a", "pcm_s16le",
                output_path,
            ]

        raise AudioRecorderError(f"Backend de grabación no soportado: {backend}")

    def start(self) -> str:
        """Inicia la grabación desde el micrófono. Devuelve el nombre del backend usado."""
        if self._is_recording:
            return self._backend or "unknown"

        backend = self._preferred_backend or self.detect_backend()
        if not backend:
            raise AudioRecorderError(
                "No se encontró ninguna herramienta de captura de audio "
                "(pw-record, parecord, arecord, sox/rec, ffmpeg o sounddevice)."
            )

        self._backend = backend

        if backend == "sounddevice":
            self._start_sounddevice()
        else:
            self._start_cli(backend)

        self._start_time = time.monotonic()
        self._is_recording = True
        return backend

    def _start_cli(self, backend: str) -> None:
        fd, path = tempfile.mkstemp(prefix="kogniterm_voice_", suffix=".wav")
        os.close(fd)
        self._temp_file = path

        cmd = self._build_cli_command(backend, path)
        logger.debug(f"Iniciando grabación de audio con {backend}: {' '.join(cmd)}")
        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:
            self._cleanup_temp_file()
            raise AudioRecorderError(f"No se pudo iniciar '{backend}': {exc}") from exc

        # Verificar brevemente que el proceso no falló inmediatamente (ej. sin micrófono)
        time.sleep(0.08)
        if self._process.poll() is not None:
            stderr_out = ""
            if self._process.stderr:
                try:
                    stderr_out = self._process.stderr.read().decode("utf-8", errors="replace").strip()
                except Exception:
                    pass
            self._process = None
            self._cleanup_temp_file()
            detail = f": {stderr_out}" if stderr_out else ""
            raise AudioRecorderError(
                f"El grabador '{backend}' terminó inesperadamente al iniciar{detail}"
            )

    def _start_sounddevice(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioRecorderError(
                "sounddevice no está instalado. Instala sounddevice o una herramienta CLI (pw-record/arecord/ffmpeg)."
            ) from exc

        self._sd_frames = []

        def _callback(indata, frames, time_info, status):  # noqa: ARG001
            with self._sd_lock:
                self._sd_frames.append(bytes(indata))

        try:
            self._sd_stream = sd.RawInputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="int16",
                callback=_callback,
            )
            self._sd_stream.start()
        except Exception as exc:
            self._sd_stream = None
            raise AudioRecorderError(f"No se pudo abrir el micrófono con sounddevice: {exc}") from exc

    def stop(self) -> Tuple[bytes, str]:
        """Detiene la grabación y retorna (audio_bytes, filename)."""
        if not self._is_recording:
            return b"", "recording.wav"

        self._is_recording = False
        self._start_time = None

        if self._backend == "sounddevice":
            return self._stop_sounddevice(), "recording.wav"
        return self._stop_cli(), "recording.wav"

    def _stop_cli(self) -> bytes:
        proc = self._process
        self._process = None

        if proc is not None and proc.poll() is None:
            try:
                # SIGINT permite que pw-record/parecord/arecord/rec/ffmpeg cierren el encabezado WAV
                if platform.system().lower() == "windows":
                    proc.terminate()
                else:
                    proc.send_signal(signal.SIGINT)
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    proc.kill()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        if proc is not None and proc.stderr:
            try:
                proc.stderr.close()
            except Exception:
                pass

        audio_bytes = b""
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                with open(self._temp_file, "rb") as f:
                    audio_bytes = f.read()
            except OSError as exc:
                logger.warning(f"No se pudo leer el audio grabado: {exc}")

        self._cleanup_temp_file()
        return audio_bytes

    def _stop_sounddevice(self) -> bytes:
        stream = self._sd_stream
        self._sd_stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

        with self._sd_lock:
            raw = b"".join(self._sd_frames)
            self._sd_frames = []

        if not raw:
            return b""

        import io
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(raw)
        return buf.getvalue()

    def cancel(self) -> None:
        """Cancela la grabación y descarta cualquier audio capturado."""
        if not self._is_recording and self._process is None and self._sd_stream is None:
            self._cleanup_temp_file()
            return

        self._is_recording = False
        self._start_time = None

        if self._backend == "sounddevice":
            stream = self._sd_stream
            self._sd_stream = None
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            with self._sd_lock:
                self._sd_frames = []
        else:
            proc = self._process
            self._process = None
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=1.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            if proc is not None and proc.stderr:
                try:
                    proc.stderr.close()
                except Exception:
                    pass
            self._cleanup_temp_file()

    def _cleanup_temp_file(self) -> None:
        path = self._temp_file
        self._temp_file = None
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
