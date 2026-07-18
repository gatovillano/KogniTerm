"""
ThreadManager: gestor unificado de hilos de chat persistentes.
Reemplaza la funcionalidad de AutosaveManager y SessionManager.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, messages_from_dict, messages_to_dict

from .chat_thread import ChatThread

logger = logging.getLogger(__name__)


class ThreadManager:
    """Gestor unificado de hilos de chat persistentes."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.threads_dir = os.path.join(workspace_dir, ".kogniterm", "threads")
        self._lock = threading.RLock()
        self._current_thread_id: Optional[str] = None

        os.makedirs(self.threads_dir, exist_ok=True)
        self._migrate_legacy_data()
        logger.info("ThreadManager inicializado en %s", self.threads_dir)

    # ------------------------------------------------------------------
    # Migración legacy
    # ------------------------------------------------------------------
    def _migrate_legacy_data(self) -> None:
        """Migra datos de autosave y sessions legacy al formato de hilos."""
        legacy_dirs = [
            os.path.join(self.workspace_dir, ".kogniterm", "autosave"),
            os.path.join(self.workspace_dir, ".kogniterm", "sessions"),
        ]
        backup_root = os.path.join(self.workspace_dir, ".kogniterm", ".backup_pre_threads")
        migrated = 0

        for legacy_dir in legacy_dirs:
            if not os.path.isdir(legacy_dir):
                continue

            for entry in os.listdir(legacy_dir):
                src = os.path.join(legacy_dir, entry)
                if not os.path.isdir(src):
                    continue

                dst = os.path.join(self.threads_dir, entry)
                if os.path.exists(dst):
                    continue

                try:
                    os.makedirs(os.path.join(backup_root, os.path.basename(legacy_dir)), exist_ok=True)
                    shutil.move(src, os.path.join(backup_root, os.path.basename(legacy_dir), entry))
                    migrated += 1
                except Exception as exc:  # pragma: no cover - logging only
                    logger.error("Error migrando %s: %s", src, exc)

        if migrated:
            logger.info("Migración legacy completada: %s hilos movidos a backup", migrated)

    # ------------------------------------------------------------------
    # CRUD de hilos
    # ------------------------------------------------------------------
    def create_thread(
        self,
        thread_id: Optional[str] = None,
        title: str = "Nueva conversación",
        messages: Optional[List[BaseMessage]] = None,
    ) -> ChatThread:
        """Crea un nuevo hilo vacío."""
        if not thread_id:
            thread_id = str(uuid.uuid4())

        with self._lock:
            thread_path = os.path.join(self.threads_dir, thread_id)
            os.makedirs(thread_path, exist_ok=True)

            now = datetime.utcnow().isoformat()
            thread = ChatThread(
                id=thread_id,
                title=title,
                created_at=now,
                updated_at=now,
                messages=list(messages or []),
            )
            self._save(thread)
            self._current_thread_id = thread_id
            return thread

    def get_thread(self, thread_id: str) -> Optional[ChatThread]:
        """Obtiene un hilo completo por ID."""
        metadata = self._load_metadata(thread_id)
        if not metadata:
            return None

        messages = self._load_messages(thread_id)
        return ChatThread(
            id=metadata["id"],
            title=metadata["title"],
            title_source=metadata.get("title_source", "manual"),
            created_at=metadata["created_at"],
            updated_at=metadata["updated_at"],
            parent_thread_id=metadata.get("parent_thread_id"),
            messages=list(messages or []),
            metadata=metadata.get("metadata", {}),
        )

    def list_threads(self) -> List[Dict[str, Any]]:
        """Lista todos los hilos, ordenados por fecha de actualización (más reciente primero)."""
        threads: List[Dict[str, Any]] = []
        with self._lock:
            if not os.path.exists(self.threads_dir):
                return []

            for entry in os.listdir(self.threads_dir):
                thread_path = os.path.join(self.threads_dir, entry)
                if not os.path.isdir(thread_path):
                    continue

                metadata = self._load_metadata(entry)
                if metadata:
                    threads.append(metadata)

        threads.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return threads

    def delete_thread(self, thread_id: str) -> bool:
        """Elimina un hilo y todo su contenido."""
        thread_path = os.path.join(self.threads_dir, thread_id)
        if not os.path.exists(thread_path):
            return False

        with self._lock:
            try:
                shutil.rmtree(thread_path)
                if self._current_thread_id == thread_id:
                    self._current_thread_id = None
                return True
            except Exception as exc:
                logger.error("Error al eliminar hilo %s: %s", thread_id, exc)
                return False

    def rename_thread(self, thread_id: str, new_title: str, source: str = "manual") -> bool:
        """Renombra un hilo."""
        with self._lock:
            thread = self.get_thread(thread_id)
            if not thread:
                return False

            thread.title = new_title
            thread.title_source = source
            thread.touch()
            return self._save(thread)

    def get_thread_metadata(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Devuelve el diccionario de metadatos del hilo (para retrocompatibilidad)."""
        return self._load_metadata(thread_id)

    def _save_metadata(self, thread_id: str, metadata: Dict[str, Any]) -> bool:
        """Guarda metadatos de un hilo (para retrocompatibilidad)."""
        with self._lock:
            thread_path = os.path.join(self.threads_dir, thread_id)
            os.makedirs(thread_path, exist_ok=True)
            metadata_file = os.path.join(thread_path, "metadata.json")
            tmp = metadata_file + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, metadata_file)
                return True
            except Exception as exc:
                logger.error("Error guardando metadatos en %s: %s", metadata_file, exc)
                return False

    def save_thread_messages(self, thread_id: str, messages: List[BaseMessage], llm_service: Optional[Any] = None) -> bool:
        """Guarda o actualiza los mensajes de un hilo y actualiza sus metadatos (para retrocompatibilidad)."""
        with self._lock:
            thread = self.get_thread(thread_id)
            if not thread:
                thread = ChatThread(
                    id=thread_id,
                    title="Nueva conversación",
                    messages=list(messages or [])
                )
            else:
                thread.messages = list(messages or [])
            
            return self.save_thread(thread, llm_service=llm_service)

    def load_thread_messages(self, thread_id: str) -> List[BaseMessage]:
        """Carga los mensajes de un hilo (para retrocompatibilidad)."""
        return self._load_messages(thread_id)

    def find_threads(self, query: str) -> List[Dict[str, Any]]:
        """Busca hilos por coincidencia parcial de ID o título (case-insensitive)."""
        if not query:
            return []
        query_lower = query.lower().strip()
        threads = self.list_threads()
        matches = []
        for t in threads:
            tid = t.get("id", "").lower()
            title = t.get("title", "").lower()
            if query_lower in tid or query_lower in title:
                matches.append(t)
        return matches

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------
    def save_thread(self, thread: ChatThread, llm_service: Optional[Any] = None) -> bool:
        """Guarda un hilo completo (mensajes + metadatos) de forma atómica."""
        with self._lock:
            thread.touch()
            success = self._save(thread)
            if success and llm_service:
                self.schedule_title_generation(thread.id, thread.messages, llm_service)
            return success

    def _save(self, thread: ChatThread) -> bool:
        """Guarda metadatos y mensajes de un hilo."""
        thread_path = os.path.join(self.threads_dir, thread.id)
        os.makedirs(thread_path, exist_ok=True)

        metadata_file = os.path.join(thread_path, "metadata.json")
        messages_file = os.path.join(thread_path, "messages.json")

        metadata = {
            "id": thread.id,
            "title": thread.title,
            "title_source": thread.title_source,
            "created_at": thread.created_at,
            "updated_at": thread.updated_at,
            "parent_thread_id": thread.parent_thread_id,
            "message_count": len(thread.messages),
            "metadata": thread.metadata,
        }

        for path, data in ((metadata_file, metadata), (messages_file, messages_to_dict(thread.messages))):
            tmp = path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            except Exception as exc:
                logger.error("Error guardando %s: %s", path, exc)
                return False

        return True

    def _load_metadata(self, thread_id: str) -> Optional[Dict[str, Any]]:
        metadata_file = os.path.join(self.threads_dir, thread_id, "metadata.json")
        if not os.path.exists(metadata_file):
            return None
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Error leyendo metadata de %s: %s", thread_id, exc)
            return None

    def _load_messages(self, thread_id: str) -> List[BaseMessage]:
        messages_file = os.path.join(self.threads_dir, thread_id, "messages.json")
        if not os.path.exists(messages_file):
            return []
        try:
            with open(messages_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return messages_from_dict(data)
        except Exception as exc:
            logger.error("Error leyendo mensajes de %s: %s", thread_id, exc)
            return []

    # ------------------------------------------------------------------
    # Hilo actual
    # ------------------------------------------------------------------
    def get_current_thread_id(self) -> Optional[str]:
        """Devuelve el ID del hilo activo actual."""
        return self._current_thread_id

    def set_current_thread_id(self, thread_id: Optional[str]) -> None:
        """Establece el hilo activo actual."""
        self._current_thread_id = thread_id

    def get_current_thread(self) -> Optional[ChatThread]:
        """Devuelve el hilo activo completo."""
        if not self._current_thread_id:
            return None
        return self.get_thread(self._current_thread_id)

    # ------------------------------------------------------------------
    # Naming automático lazy
    # ------------------------------------------------------------------
    def schedule_title_generation(
        self,
        thread_id: str,
        messages: List[BaseMessage],
        llm_service: Any,
    ) -> None:
        """Lanza una tarea en background para generar título si aplica."""
        if not thread_id:
            return

        metadata = self._load_metadata(thread_id)
        if not metadata:
            return

        current_title = metadata.get("title", "")
        default_titles = {"Nueva conversación", "Nueva Conversación", "Conversación sin título", "Conversación", ""}
        is_generic = current_title in default_titles or current_title == thread_id

        if not is_generic or metadata.get("title_source") == "llm":
            return

        # Verificar que tengamos al menos un HumanMessage y un AIMessage
        human_msgs = [m for m in messages if getattr(m, "type", None) == "human" or isinstance(m, HumanMessage)]
        ai_msgs = [m for m in messages if getattr(m, "type", None) == "ai" or isinstance(m, AIMessage)]
        if not human_msgs or not ai_msgs:
            return

        try:
            asyncio.get_running_loop().create_task(
                self._generate_title(thread_id, messages, llm_service)
            )
        except RuntimeError:
            # Si no hay un bucle de eventos corriendo, se ignora
            pass

    async def _generate_title(
        self,
        thread_id: str,
        messages: List[BaseMessage],
        llm_service: Any,
    ) -> Optional[str]:
        """Genera un título con LLM y lo persiste si es bueno."""
        try:
            human_msgs: List[str] = []
            ai_msgs: List[str] = []

            for m in messages:
                content = m.content
                if isinstance(content, list):
                    text_parts = [
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict) and part.get("type") == "text"
                    ]
                    content = " ".join(text_parts)

                if not isinstance(content, str) or not content.strip():
                    continue

                if getattr(m, "type", None) == "human" or isinstance(m, HumanMessage):
                    human_msgs.append(content.strip())
                elif getattr(m, "type", None) == "ai" or isinstance(m, AIMessage):
                    ai_msgs.append(content.strip())

            if not human_msgs or not ai_msgs:
                return None

            prompt = (
                "Genera un título conciso (máximo 5-6 palabras) para este hilo de conversación. "
                "Solo responde con el título, sin comillas, markdown ni explicaciones.\n\n"
                f"Usuario: {human_msgs[0][:300]}\n"
                f"Asistente: {ai_msgs[0][:300]}"
            )

            title = await self._call_llm_for_title(prompt, llm_service)
            if title:
                title = title.strip().strip("\"'").replace("\n", " ").strip()
                for prefix in ("título:", "title:", "asunto:", "subject:"):
                    if title.lower().startswith(prefix):
                        title = title[len(prefix):].strip()
                title = title.strip("\"'")
                words = title.split()
                if len(words) > 7:
                    title = " ".join(words[:6]) + "..."
            if not title:
                title = self._fallback_title(human_msgs[0])

            self.rename_thread(thread_id, title, source="llm")
            return title
        except Exception as exc:
            logger.error("Error generando título para hilo %s: %s", thread_id, exc)
            return None

    async def _call_llm_for_title(self, prompt: str, llm_service: Any) -> Optional[str]:
        """Llama al LLM para generar un título."""
        loop = asyncio.get_running_loop()

        def do_call() -> Optional[str]:
            try:
                if hasattr(llm_service, "use_multi_provider") and llm_service.use_multi_provider:
                    generator = llm_service.provider_manager.execute_with_fallback(
                        model_name=llm_service.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        stream=False,
                        max_tokens=15,
                        temperature=0.3,
                        api_key=getattr(llm_service, "api_key", None),
                        api_base=getattr(llm_service, "api_base", None),
                        headers=getattr(llm_service, "headers", None),
                    )
                    response = next(generator)
                else:
                    from litellm import completion

                    kwargs: Dict[str, Any] = {
                        "model": llm_service.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 15,
                        "temperature": 0.3,
                    }
                    api_key = getattr(llm_service, "api_key", None)
                    api_base = getattr(llm_service, "api_base", None)
                    if api_key:
                        kwargs["api_key"] = api_key
                    if api_base:
                        kwargs["api_base"] = api_base
                    if "kilocode" in llm_service.model_name.lower() or (api_base and "kilo.ai" in api_base):
                        kwargs["custom_llm_provider"] = "openai"

                    response = completion(**kwargs)

                content_val = self._extract_content(response)
                return content_val.strip().strip("\"'") if isinstance(content_val, str) else None
            except Exception as exc:
                logger.error("Error en llamada LLM para título: %s", exc)
                return None

        return await loop.run_in_executor(None, do_call)

    @staticmethod
    def _extract_content(response: Any) -> Optional[str]:
        if response is None:
            return None
        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and choice.message:
                return getattr(choice.message, "content", None)
        if isinstance(response, dict):
            choices = response.get("choices", [])
            if choices:
                choice = choices[0]
                message = (
                    choice.get("message", {})
                    if isinstance(choice, dict)
                    else getattr(choice, "message", None)
                )
                if isinstance(message, dict):
                    return message.get("content")
                if message is not None:
                    return getattr(message, "content", None)
        return None

    @staticmethod
    def _fallback_title(first_user_message: str) -> str:
        text = " ".join(first_user_message.split())[:40]
        return text if text else "Conversación"
