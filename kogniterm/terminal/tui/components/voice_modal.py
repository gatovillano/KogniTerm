"""
Modal interactivo de dictado por voz para la TUI de KogniTerm.

Replica el flujo de transcripción de audio de KogniTerm Desktop:
- Captura audio desde el micrófono con indicador animado y temporizador.
- Permite detener y transcribir (Enter / Espacio / botón) o cancelar (Esc / botón).
- Transcribe mediante el servidor (/api/audio/transcribe) con fallback local
  a AudioTranscriptionService (faster-whisper).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

from kogniterm.core.audio_recorder import AudioRecorder, AudioRecorderError
from kogniterm.terminal.themes import ColorPalette
from kogniterm.terminal.tui.components.settings_modals import BaseModal

logger = logging.getLogger(__name__)


_WAVE_FRAMES = [
    "▂ ▅ ▇ ▃ ▆ ▄ ▂",
    "▄ ▇ ▅ ▆ ▃ ▇ ▄",
    "▆ ▃ ▇ ▅ ▇ ▂ ▅",
    "▃ ▆ ▄ ▇ ▅ ▆ ▃",
    "▅ ▂ ▆ ▄ ▇ ▃ ▆",
    "▇ ▄ ▃ ▆ ▂ ▅ ▇",
]

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _format_seconds(secs: float) -> str:
    total = max(0, int(secs))
    m, s = divmod(total, 60)
    return f"{m}:{s:02d}"


class VoiceDictationModal(BaseModal):
    """Modal command-palette para grabar audio y transcribirlo con Faster-Whisper."""

    DEFAULT_CSS = BaseModal.CSS + """
    #voice-body {
        width: 100%;
        height: auto;
        padding: 1 4 2 4;
    }
    #voice-status {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        margin-bottom: 1;
    }
    #voice-wave {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        margin-bottom: 1;
    }
    #voice-hint {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        margin-bottom: 1;
    }
    #voice-actions {
        width: 100%;
        height: 3;
        align: center middle;
    }
    #voice-actions Button {
        margin: 0 1;
        min-width: 18;
    }
    """

    def __init__(
        self,
        language: Optional[str] = None,
        recorder: Optional[AudioRecorder] = None,
        use_server: bool = False,
    ):
        super().__init__()
        self.language = language
        self._recorder = recorder or AudioRecorder()
        self._use_server = use_server
        self._state = "starting"  # starting | recording | transcribing | error
        self._frame_idx = 0
        self._timer = None
        self._model_label = os.getenv("KOGNITERM_WHISPER_MODEL", "base")

    def _build_css(self) -> str:
        p = ColorPalette
        return super()._build_css() + """
        #voice-body { background: %s; }
        #voice-hint { color: %s; }
        """ % (p.GRAY_800, p.TEXT_MUTED)

    def compose(self) -> ComposeResult:
        lang_badge = f" · {self.language}" if self.language else ""
        with Vertical(id="palette-shell"):
            with Horizontal(id="palette-header"):
                yield Label("🎤 Dictado por voz", id="palette-title-label")
                yield Label(
                    f"Faster-Whisper {self._model_label}{lang_badge}",
                    id="palette-hint-label",
                )
            with Vertical(id="voice-body"):
                yield Static("Iniciando micrófono…", id="voice-status", markup=True)
                yield Static("", id="voice-wave", markup=True)
                yield Static(
                    "Enter / Espacio: detener y transcribir  ·  Esc: cancelar",
                    id="voice-hint",
                    markup=True,
                )
                with Horizontal(id="voice-actions"):
                    yield Button(
                        "Detener y transcribir",
                        id="btn-voice-stop",
                        variant="success",
                    )
                    yield Button(
                        "Cancelar",
                        id="btn-voice-cancel",
                        variant="error",
                    )

    def on_mount(self) -> None:
        super().on_mount()
        try:
            backend = self._recorder.start()
            self._state = "recording"
            logger.debug(f"VoiceDictationModal grabando con backend '{backend}'")
            self._update_visuals()
            self._timer = self.set_interval(0.15, self._on_tick)
        except AudioRecorderError as exc:
            self._enter_error(str(exc))
        except Exception as exc:
            self._enter_error(f"Error al iniciar el micrófono: {exc}")

    def on_unmount(self) -> None:
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None
        if self._recorder.is_recording:
            self._recorder.cancel()

    def _on_tick(self) -> None:
        self._frame_idx += 1
        self._update_visuals()

    def _update_visuals(self) -> None:
        p = ColorPalette
        try:
            status_w = self.query_one("#voice-status", Static)
            wave_w = self.query_one("#voice-wave", Static)
            hint_w = self.query_one("#voice-hint", Static)
        except Exception:
            return

        if self._state == "recording":
            elapsed = _format_seconds(self._recorder.elapsed_seconds)
            wave = _WAVE_FRAMES[self._frame_idx % len(_WAVE_FRAMES)]
            status_w.update(
                f"[{p.ERROR} bold]● Grabando ({elapsed})[/{p.ERROR} bold]"
            )
            wave_w.update(f"[{p.ERROR}]{wave}[/{p.ERROR}]")
            hint_w.update(
                f"[{p.TEXT_MUTED}]Habla ahora…  [bold]Enter[/bold] / [bold]Espacio[/bold] para transcribir  ·  [bold]Esc[/bold] para cancelar[/{p.TEXT_MUTED}]"
            )
        elif self._state == "transcribing":
            spin = _SPINNER_FRAMES[self._frame_idx % len(_SPINNER_FRAMES)]
            status_w.update(
                f"[{p.WARNING} bold]{spin} Transcribiendo audio…[/{p.WARNING} bold]"
            )
            wave_w.update(
                f"[{p.TEXT_MUTED}]Procesando con Faster-Whisper {self._model_label}[/{p.TEXT_MUTED}]"
            )
            hint_w.update(f"[{p.TEXT_DIM}]Por favor espera…[/{p.TEXT_DIM}]")

    def _enter_error(self, message: str) -> None:
        self._state = "error"
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None
        p = ColorPalette
        try:
            self.query_one("#voice-status", Static).update(
                f"[{p.ERROR} bold]✖ No se pudo grabar/transcribir[/{p.ERROR} bold]"
            )
            self.query_one("#voice-wave", Static).update(
                f"[{p.TEXT_SECONDARY}]{message}[/{p.TEXT_SECONDARY}]"
            )
            self.query_one("#voice-hint", Static).update(
                f"[{p.TEXT_MUTED}]Presiona Enter o Esc para cerrar[/{p.TEXT_MUTED}]"
            )
            stop_btn = self.query_one("#btn-voice-stop", Button)
            stop_btn.display = False
            cancel_btn = self.query_one("#btn-voice-cancel", Button)
            cancel_btn.label = "Cerrar"
        except Exception:
            pass

    def _cancel_and_dismiss(self) -> None:
        if self._recorder.is_recording:
            self._recorder.cancel()
        self.dismiss(None)

    def _stop_and_transcribe(self) -> None:
        if self._state != "recording":
            return
        self._state = "transcribing"
        try:
            self.query_one("#btn-voice-stop", Button).disabled = True
            self.query_one("#btn-voice-cancel", Button).disabled = True
        except Exception:
            pass
        self._update_visuals()
        self.run_worker(self._transcribe_worker(), exclusive=True)

    async def _transcribe_worker(self) -> None:
        try:
            audio_bytes, filename = await asyncio.to_thread(self._recorder.stop)
            if not audio_bytes or len(audio_bytes) <= 44:
                # 44 bytes es solo el header WAV vacío
                self.dismiss("")
                return

            result = await self._transcribe_bytes(audio_bytes, filename)
            text = (result.get("text") or "").strip()
            self.dismiss(text)
        except Exception as exc:
            logger.error(f"Error transcribiendo audio en TUI: {exc}", exc_info=True)
            self._enter_error(str(exc))

    async def _transcribe_bytes(self, audio_bytes: bytes, filename: str) -> dict:
        """Transcribe usando el servidor si está activo, con fallback local a faster-whisper."""
        if self._use_server:
            try:
                from kogniterm.terminal.api_client_tui import transcribe_audio
                return await transcribe_audio(
                    audio_bytes,
                    filename=filename,
                    language=self.language,
                )
            except Exception as exc:
                logger.debug(
                    f"Servidor no disponible para transcribir audio ({exc}), usando faster-whisper local."
                )

        from kogniterm.core.audio_service import AudioTranscriptionService
        service = AudioTranscriptionService.get_instance()
        return await service.transcribe_audio(
            audio_bytes,
            filename=filename,
            language=self.language,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-voice-stop":
            self._stop_and_transcribe()
        elif event.button.id == "btn-voice-cancel":
            self._cancel_and_dismiss()

    def on_key(self, event: events.Key) -> None:
        if self._state == "recording":
            if event.key in ("enter", "space"):
                event.prevent_default()
                event.stop()
                self._stop_and_transcribe()
            elif event.key == "escape":
                event.prevent_default()
                event.stop()
                self._cancel_and_dismiss()
        elif self._state == "error":
            if event.key in ("enter", "escape", "space"):
                event.prevent_default()
                event.stop()
                self.dismiss(None)
        elif self._state == "transcribing":
            if event.key == "escape":
                event.prevent_default()
                event.stop()
                self.dismiss(None)
