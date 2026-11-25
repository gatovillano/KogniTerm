import asyncio
import io
import math
import os
import struct
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from kogniterm.core.audio_recorder import AudioRecorder, AudioRecorderError
from kogniterm.terminal.tui.command_processor import TUICommandProcessor
from kogniterm.terminal.tui.components.voice_modal import VoiceDictationModal


def _make_wav_bytes(duration_sec: float = 0.1, sample_rate: int = 16000) -> bytes:
    num_samples = int(sample_rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            sample = int(32767.0 * 0.1 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            wf.writeframes(struct.pack("<h", sample))
    return buf.getvalue()


# ── AudioRecorder tests ──────────────────────────────────────────────────────


def test_audio_recorder_detect_backend_linux():
    with patch("platform.system", return_value="Linux"), patch(
        "shutil.which", side_effect=lambda name: "/usr/bin/parecord" if name == "parecord" else None
    ):
        assert AudioRecorder.detect_backend() == "parecord"


def test_audio_recorder_build_cli_commands():
    rec = AudioRecorder()
    assert rec._build_cli_command("pw-record", "/tmp/a.wav")[0] == "pw-record"
    assert "--rate=16000" in rec._build_cli_command("parecord", "/tmp/a.wav")
    assert "arecord" == rec._build_cli_command("arecord", "/tmp/a.wav")[0]
    assert "rec" == rec._build_cli_command("rec", "/tmp/a.wav")[0]
    assert "ffmpeg" == rec._build_cli_command("ffmpeg", "/tmp/a.wav")[0]


def test_audio_recorder_no_backend_raises():
    rec = AudioRecorder()
    with patch.object(AudioRecorder, "detect_backend", return_value=None):
        with pytest.raises(AudioRecorderError, match="herramienta de captura"):
            rec.start()


def test_audio_recorder_cli_start_stop_and_cleanup():
    wav_payload = _make_wav_bytes(0.05)

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            self.output_path = cmd[-1]
            self._alive = True
            self.stderr = io.BytesIO(b"")
            with open(self.output_path, "wb") as f:
                f.write(wav_payload)

        def poll(self):
            return None if self._alive else 0

        def send_signal(self, sig):
            self._alive = False

        def terminate(self):
            self._alive = False

        def wait(self, timeout=None):
            self._alive = False
            return 0

    rec = AudioRecorder(backend="pw-record")
    with patch("subprocess.Popen", side_effect=FakePopen):
        backend = rec.start()
        assert backend == "pw-record"
        assert rec.is_recording is True
        temp_path = rec._temp_file
        assert temp_path and os.path.exists(temp_path)

        data, filename = rec.stop()
        assert data == wav_payload
        assert filename == "recording.wav"
        assert rec.is_recording is False
        assert not os.path.exists(temp_path)


def test_audio_recorder_cancel_cleans_up():
    class FakePopen:
        def __init__(self, cmd, **kwargs):
            self.output_path = cmd[-1]
            self._alive = True
            self.stderr = io.BytesIO(b"")

        def poll(self):
            return None if self._alive else 0

        def terminate(self):
            self._alive = False

        def wait(self, timeout=None):
            self._alive = False
            return 0

    rec = AudioRecorder(backend="arecord")
    with patch("subprocess.Popen", side_effect=FakePopen):
        rec.start()
        temp_path = rec._temp_file
        rec.cancel()
        assert rec.is_recording is False
        assert temp_path and not os.path.exists(temp_path)


# ── TUICommandProcessor /voice & /dictate tests ──────────────────────────────


class _FakeChatInput:
    def __init__(self, initial_text: str = ""):
        self.text = initial_text
        self.cursor_location = (0, 0)
        self.focused = False

    @property
    def document(self):
        return SimpleNamespace(lines=self.text.split("\n"))

    def focus(self):
        self.focused = True


@pytest.mark.asyncio
async def test_command_processor_voice_inserts_into_chat_input():
    fake_input = _FakeChatInput(initial_text="")
    fake_ui = MagicMock()
    fake_ui.ask_voice_dictation_async = AsyncMock(return_value="hola mundo desde voz")
    fake_ui.print_message = MagicMock()

    fake_app = MagicMock()
    fake_app.tui_ui = fake_ui
    fake_app.query_one = MagicMock(return_value=fake_input)

    proc = TUICommandProcessor(fake_app)
    handled = await proc.process_command("/voice es")

    assert handled is True
    fake_ui.ask_voice_dictation_async.assert_awaited_once_with(language="es")
    assert fake_input.text == "hola mundo desde voz"
    assert fake_input.cursor_location == (0, len("hola mundo desde voz"))
    assert fake_input.focused is True


@pytest.mark.asyncio
async def test_command_processor_dictate_appends_to_existing_draft():
    fake_input = _FakeChatInput(initial_text="Explica esto:")
    fake_ui = MagicMock()
    fake_ui.ask_voice_dictation_async = AsyncMock(return_value="cómo funciona el módulo")
    fake_ui.print_message = MagicMock()

    fake_app = MagicMock()
    fake_app.tui_ui = fake_ui
    fake_app.query_one = MagicMock(return_value=fake_input)

    proc = TUICommandProcessor(fake_app)
    handled = await proc.process_command("/dictate")

    assert handled is True
    fake_ui.ask_voice_dictation_async.assert_awaited_once_with(language=None)
    assert fake_input.text == "Explica esto: cómo funciona el módulo"
    assert fake_input.focused is True


@pytest.mark.asyncio
async def test_command_processor_voice_cancel_and_empty():
    fake_input = _FakeChatInput(initial_text="borrador")
    fake_ui = MagicMock()
    fake_ui.print_message = MagicMock()
    fake_app = MagicMock()
    fake_app.tui_ui = fake_ui
    fake_app.query_one = MagicMock(return_value=fake_input)
    proc = TUICommandProcessor(fake_app)

    # Cancel (None)
    fake_ui.ask_voice_dictation_async = AsyncMock(return_value=None)
    assert await proc.process_command("/voice") is True
    assert fake_input.text == "borrador"
    fake_ui.print_message.assert_not_called()

    # Empty speech ("")
    fake_ui.ask_voice_dictation_async = AsyncMock(return_value="   ")
    assert await proc.process_command("%dictate") is True
    assert fake_input.text == "borrador"
    fake_ui.print_message.assert_called_once()


# ── VoiceDictationModal UI tests (Textual pilot) ─────────────────────────────


class _ModalHostApp(App):
    def compose(self) -> ComposeResult:
        yield Static("host")


class _MockRecorder:
    def __init__(self, payload: bytes = b"", fail_start: bool = False):
        self.payload = payload
        self.fail_start = fail_start
        self.is_recording = False
        self.cancelled = False
        self.elapsed_seconds = 1.2

    def start(self) -> str:
        if self.fail_start:
            raise AudioRecorderError("Micrófono no encontrado")
        self.is_recording = True
        return "mock"

    def stop(self):
        self.is_recording = False
        return self.payload, "recording.wav"

    def cancel(self):
        self.is_recording = False
        self.cancelled = True


@pytest.mark.asyncio
async def test_voice_modal_enter_transcribes_and_dismisses():
    wav_data = _make_wav_bytes(0.1)
    mock_rec = _MockRecorder(payload=wav_data)
    result_holder = []

    app = _ModalHostApp()
    async with app.run_test() as pilot:
        modal = VoiceDictationModal(language="es", recorder=mock_rec, use_server=False)
        with patch(
            "kogniterm.core.audio_service.AudioTranscriptionService.get_instance"
        ) as mock_get_inst:
            mock_service = MagicMock()
            mock_service.transcribe_audio = AsyncMock(
                return_value={"text": "prueba de dictado", "language": "es", "duration": 0.1}
            )
            mock_get_inst.return_value = mock_service

            app.push_screen(modal, callback=result_holder.append)
            await pilot.pause()
            assert mock_rec.is_recording is True

            await pilot.press("enter")
            # Esperar a que el worker asíncrono termine
            for _ in range(20):
                await pilot.pause(0.05)
                if result_holder:
                    break

    assert result_holder == ["prueba de dictado"]
    assert mock_rec.is_recording is False


@pytest.mark.asyncio
async def test_voice_modal_escape_cancels():
    mock_rec = _MockRecorder(payload=_make_wav_bytes(0.1))
    result_holder = []

    app = _ModalHostApp()
    async with app.run_test() as pilot:
        modal = VoiceDictationModal(recorder=mock_rec, use_server=False)
        app.push_screen(modal, callback=result_holder.append)
        await pilot.pause()
        assert mock_rec.is_recording is True

        await pilot.press("escape")
        await pilot.pause()

    assert result_holder == [None]
    assert mock_rec.cancelled is True


@pytest.mark.asyncio
async def test_voice_modal_recorder_error_dismisses_on_escape():
    mock_rec = _MockRecorder(fail_start=True)
    result_holder = []

    app = _ModalHostApp()
    async with app.run_test() as pilot:
        modal = VoiceDictationModal(recorder=mock_rec, use_server=False)
        app.push_screen(modal, callback=result_holder.append)
        await pilot.pause()
        assert modal._state == "error"

        await pilot.press("escape")
        await pilot.pause()

    assert result_holder == [None]


@pytest.mark.asyncio
async def test_voice_modal_server_fallback_to_local():
    wav_data = _make_wav_bytes(0.1)
    mock_rec = _MockRecorder(payload=wav_data)
    modal = VoiceDictationModal(language="es", recorder=mock_rec, use_server=True)

    with patch(
        "kogniterm.terminal.api_client_tui.transcribe_audio",
        new=AsyncMock(side_effect=RuntimeError("server offline")),
    ), patch(
        "kogniterm.core.audio_service.AudioTranscriptionService.get_instance"
    ) as mock_get_inst:
        mock_service = MagicMock()
        mock_service.transcribe_audio = AsyncMock(
            return_value={"text": "fallback local ok", "language": "es", "duration": 0.1}
        )
        mock_get_inst.return_value = mock_service

        res = await modal._transcribe_bytes(wav_data, "recording.wav")
        assert res["text"] == "fallback local ok"
        mock_service.transcribe_audio.assert_awaited_once_with(
            wav_data, filename="recording.wav", language="es"
        )
