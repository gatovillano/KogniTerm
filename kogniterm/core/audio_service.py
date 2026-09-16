"""
Servicio de transcripción de audio para KogniTerm utilizando faster-whisper.
Utiliza un modelo Whisper ligero ("tiny" por defecto) cuantizado en int8 para CPU.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from typing import Optional, Dict, Any

logger = logging.getLogger("kogniterm.core.audio_service")

class AudioTranscriptionService:
    """Servicio singleton para transcripción de audio con Whisper ligero."""
    
    _instance: Optional[AudioTranscriptionService] = None
    
    def __init__(self, model_size: Optional[str] = None):
        self.model_size = model_size or os.getenv("KOGNITERM_WHISPER_MODEL", "tiny")
        self.device = os.getenv("KOGNITERM_WHISPER_DEVICE", "cpu")
        self.compute_type = os.getenv("KOGNITERM_WHISPER_COMPUTE_TYPE", "int8")
        self._model = None
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> AudioTranscriptionService:
        if cls._instance is None:
            cls._instance = AudioTranscriptionService()
        return cls._instance

    def _get_or_load_model(self):
        """Carga perezosa del modelo Whisper para no demorar el inicio del servidor."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(
                    f"Cargando modelo Whisper '{self.model_size}' en {self.device} con {self.compute_type}..."
                )
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info("Modelo Whisper cargado exitosamente.")
            except Exception as e:
                logger.error(f"Error al inicializar el modelo Whisper: {e}")
                raise RuntimeError(f"No se pudo cargar el modelo Whisper: {e}") from e
        return self._model

    def _sync_transcribe(
        self,
        file_path: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ejecuta la transcripción síncrona en un hilo separado."""
        model = self._get_or_load_model()
        segments, info = model.transcribe(
            file_path,
            language=language,
            beam_size=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        text_parts = []
        for segment in segments:
            clean = segment.text.strip()
            if clean:
                text_parts.append(clean)
                
        full_text = " ".join(text_parts).strip()
        return {
            "text": full_text,
            "language": info.language,
            "language_probability": getattr(info, "language_probability", 1.0),
            "duration": round(getattr(info, "duration", 0.0), 2)
        }

    async def transcribe_audio(
        self,
        file_bytes: bytes,
        filename: str = "audio.webm",
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transcribe un archivo de audio en memoria.
        Guarda los bytes temporalmente y procesa en un thread pool.
        """
        if not file_bytes:
            return {"text": "", "language": language or "unknown", "duration": 0.0}

        ext = os.path.splitext(filename)[1] or ".webm"
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                temp_file = f.name
                f.write(file_bytes)
                f.flush()

            # Ejecutar en hilo para no bloquear el event loop asíncrono
            result = await asyncio.to_thread(self._sync_transcribe, temp_file, language)
            return result
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError as err:
                    logger.warning(f"No se pudo eliminar el archivo temporal de audio {temp_file}: {err}")

    def get_status(self) -> Dict[str, Any]:
        """Devuelve el estado del servicio de transcripción."""
        return {
            "available": True,
            "model": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "loaded": self._model is not None
        }

# Instancia por defecto
audio_service = AudioTranscriptionService.get_instance()
