import { useState, useRef, useCallback, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';

export interface UseAudioTranscriptionResult {
  isRecording: boolean;
  isTranscribing: boolean;
  recordingDuration: number;
  audioError: string | null;
  startRecording: () => Promise<boolean>;
  stopRecording: () => Promise<string | null>;
  cancelRecording: () => void;
  clearError: () => void;
}

export const useAudioTranscription = (): UseAudioTranscriptionResult => {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isTranscribing, setIsTranscribing] = useState<boolean>(false);
  const [recordingDuration, setRecordingDuration] = useState<number>(0);
  const [audioError, setAudioError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const mimeTypeRef = useRef<string>('audio/webm');

  // Limpiar temporizador y stream al desmontar el componente
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const clearError = useCallback(() => {
    setAudioError(null);
  }, []);

  const getSupportedMimeType = (): string => {
    if (typeof MediaRecorder === 'undefined') return '';
    const preferredTypes = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/ogg',
      'audio/mp4',
      'audio/wav',
    ];
    for (const type of preferredTypes) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return '';
  };

  const startRecording = useCallback(async (): Promise<boolean> => {
    clearError();

    if (!navigator?.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setAudioError('La grabación de audio no está disponible en este entorno.');
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const mimeType = getSupportedMimeType();
      mimeTypeRef.current = mimeType || 'audio/webm';

      const options: MediaRecorderOptions = mimeType ? { mimeType } : {};
      const recorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e: BlobEvent) => {
        if (e.data && e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.start(250); // Emitir chunks cada 250ms
      setIsRecording(true);
      setRecordingDuration(0);

      const startTime = Date.now();
      timerRef.current = window.setInterval(() => {
        setRecordingDuration(Math.floor((Date.now() - startTime) / 1000));
      }, 500);

      return true;
    } catch (err: any) {
      console.error('Error al iniciar grabación:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setAudioError('Permiso para acceder al micrófono denegado.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setAudioError('No se detectó ningún micrófono en el sistema.');
      } else {
        setAudioError(`Error al acceder al micrófono: ${err.message || err}`);
      }
      return false;
    }
  }, [clearError]);

  const stopRecording = useCallback(async (): Promise<string | null> => {
    if (!mediaRecorderRef.current || !isRecording) {
      return null;
    }

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    const recorder = mediaRecorderRef.current;

    return new Promise<string | null>((resolve) => {
      recorder.onstop = async () => {
        setIsRecording(false);

        // Detener y liberar el stream del micrófono
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }

        const mime = mimeTypeRef.current || 'audio/webm';
        const audioBlob = new Blob(audioChunksRef.current, { type: mime });
        audioChunksRef.current = [];

        // Si el audio es demasiado corto o vacío, no enviar
        if (audioBlob.size < 500) {
          resolve(null);
          return;
        }

        setIsTranscribing(true);
        try {
          const extension = mime.includes('ogg') ? 'ogg' : mime.includes('wav') ? 'wav' : 'webm';
          const formData = new FormData();
          formData.append('file', audioBlob, `input_voice.${extension}`);

          const response = await fetch(`${API_BASE_URL}/api/audio/transcribe`, {
            method: 'POST',
            body: formData,
          });

          if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Error del servidor (${response.status})`);
          }

          const data = await response.json();
          const transcribedText = (data?.text || '').trim();
          resolve(transcribedText || null);
        } catch (err: any) {
          console.error('Error durante la transcripción de audio:', err);
          setAudioError(`Error al transcribir: ${err.message || 'Error desconocido'}`);
          resolve(null);
        } finally {
          setIsTranscribing(false);
        }
      };

      try {
        recorder.stop();
      } catch (err) {
        console.error('Error al detener MediaRecorder:', err);
        setIsRecording(false);
        resolve(null);
      }
    });
  }, [isRecording]);

  const cancelRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // Ignorar
      }
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    audioChunksRef.current = [];
    setIsRecording(false);
    setIsTranscribing(false);
    setRecordingDuration(0);
  }, []);

  return {
    isRecording,
    isTranscribing,
    recordingDuration,
    audioError,
    startRecording,
    stopRecording,
    cancelRecording,
    clearError,
  };
};
