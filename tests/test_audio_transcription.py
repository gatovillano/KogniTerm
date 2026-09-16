import io
import math
import struct
import wave
import pytest
from fastapi.testclient import TestClient

from kogniterm.server.app import create_app, API_TOKEN
from kogniterm.core.audio_service import AudioTranscriptionService


def generate_test_wav_bytes(duration_sec: float = 0.5, freq: float = 440.0, sample_rate: int = 16000) -> bytes:
    """Genera un archivo WAV en memoria con un tono puro para pruebas."""
    num_samples = int(sample_rate * duration_sec)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(num_samples):
            sample = int(32767.0 * 0.1 * math.sin(2.0 * math.pi * freq * i / sample_rate))
            wf.writeframes(struct.pack("<h", sample))
    return buf.getvalue()


@pytest.mark.asyncio
async def test_audio_service_empty():
    service = AudioTranscriptionService.get_instance()
    res = await service.transcribe_audio(b"", "empty.wav")
    assert res["text"] == ""
    assert res["duration"] == 0.0


@pytest.mark.asyncio
async def test_audio_service_status():
    service = AudioTranscriptionService.get_instance()
    status = service.get_status()
    assert status["available"] is True
    assert status["model"] in ("tiny", "base", "tiny.en")
    assert status["device"] == "cpu"
    assert status["compute_type"] == "int8"


@pytest.mark.asyncio
async def test_audio_service_transcribe_wav():
    service = AudioTranscriptionService.get_instance()
    wav_bytes = generate_test_wav_bytes(duration_sec=0.5)
    res = await service.transcribe_audio(wav_bytes, "test.wav")
    assert "text" in res
    assert "language" in res
    assert isinstance(res["duration"], float)


def test_api_audio_status():
    app = create_app()
    client = TestClient(app)
    response = client.get("/api/audio/status")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert "model" in data


def test_api_audio_transcribe_empty():
    app = create_app()
    client = TestClient(app)
    files = {"file": ("empty.wav", b"", "audio/wav")}
    response = client.post("/api/audio/transcribe", files=files)
    assert response.status_code == 400


def test_api_audio_transcribe_valid_wav():
    app = create_app()
    client = TestClient(app)
    wav_bytes = generate_test_wav_bytes(duration_sec=0.5)
    files = {"file": ("test.wav", wav_bytes, "audio/wav")}
    data = {"language": "es"}
    response = client.post("/api/audio/transcribe", files=files, data=data)
    assert response.status_code == 200
    res_data = response.json()
    assert "text" in res_data
    assert "language" in res_data
    assert "duration" in res_data
