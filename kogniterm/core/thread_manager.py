import os
import json
import uuid
import logging
import threading
from typing import List, Dict, Optional, Any
from datetime import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, messages_to_dict, messages_from_dict
import asyncio

logger = logging.getLogger(__name__)

class ThreadManager:
    """Gestor de hilos de chat persistentes con nombrado automático."""
    
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.threads_dir = os.path.join(workspace_dir, ".kogniterm", "threads")
        self._lock = threading.RLock()
        
        # Crear directorio si no existe
        os.makedirs(self.threads_dir, exist_ok=True)
        logger.info(f"ThreadManager inicializado en {self.threads_dir}")

    def create_thread(self, thread_id: Optional[str] = None, title: str = "Nueva conversación") -> Dict:
        """Crea un nuevo hilo vacío."""
        if not thread_id:
            thread_id = str(uuid.uuid4())
            
        with self._lock:
            thread_path = os.path.join(self.threads_dir, thread_id)
            os.makedirs(thread_path, exist_ok=True)
            
            now = datetime.utcnow().isoformat()
            metadata = {
                "id": thread_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
                "has_generated_title": False
            }
            
            self._save_metadata(thread_id, metadata)
            self._save_messages(thread_id, [])
            
            return metadata

    def list_threads(self) -> List[Dict]:
        """Lista todos los hilos, ordenados por fecha de actualización (más reciente primero)."""
        threads = []
        with self._lock:
            if not os.path.exists(self.threads_dir):
                return []
                
            for entry in os.listdir(self.threads_dir):
                thread_path = os.path.join(self.threads_dir, entry)
                if os.path.isdir(thread_path):
                    metadata = self.get_thread_metadata(entry)
                    if metadata:
                        threads.append(metadata)
                        
            # Ordenar por updated_at descendente
            threads.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            return threads

    def get_thread_metadata(self, thread_id: str) -> Optional[Dict]:
        """Obtiene los metadatos de un hilo."""
        metadata_file = os.path.join(self.threads_dir, thread_id, "metadata.json")
        if not os.path.exists(metadata_file):
            return None
            
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error al leer metadatos de hilo {thread_id}: {e}")
            return None

    def _save_metadata(self, thread_id: str, metadata: Dict) -> bool:
        """Guarda metadatos de un hilo."""
        metadata_file = os.path.join(self.threads_dir, thread_id, "metadata.json")
        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error al guardar metadatos de hilo {thread_id}: {e}")
            return False

    def load_thread_messages(self, thread_id: str) -> Optional[List[BaseMessage]]:
        """Carga los mensajes de un hilo."""
        messages_file = os.path.join(self.threads_dir, thread_id, "messages.json")
        if not os.path.exists(messages_file):
            return None
            
        try:
            with open(messages_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return messages_from_dict(data)
        except Exception as e:
            logger.error(f"Error al cargar mensajes del hilo {thread_id}: {e}")
            return None

    def save_thread_messages(self, thread_id: str, messages: List[BaseMessage]) -> bool:
        """Guarda mensajes en un hilo y actualiza sus metadatos."""
        with self._lock:
            # Asegurarnos que el hilo existe
            metadata = self.get_thread_metadata(thread_id)
            if not metadata:
                metadata = self.create_thread(thread_id=thread_id)
            
            # Guardar mensajes
            if not self._save_messages(thread_id, messages):
                return False
                
            # Actualizar metadatos
            metadata["updated_at"] = datetime.utcnow().isoformat()
            metadata["message_count"] = len(messages)
            
            return self._save_metadata(thread_id, metadata)
            
    def _save_messages(self, thread_id: str, messages: List[BaseMessage]) -> bool:
        """Guarda mensajes internamente (requiere que el directorio exista)."""
        messages_file = os.path.join(self.threads_dir, thread_id, "messages.json")
        
        try:
            messages_dict = messages_to_dict(messages)
            
            # Guardado seguro con archivo temporal
            tmp_file = messages_file + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(messages_dict, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
                
            os.replace(tmp_file, messages_file)
            return True
        except Exception as e:
            logger.error(f"Error al guardar mensajes del hilo {thread_id}: {e}")
            return False

    def delete_thread(self, thread_id: str) -> bool:
        """Elimina un hilo y todo su contenido."""
        import shutil
        thread_path = os.path.join(self.threads_dir, thread_id)
        if not os.path.exists(thread_path):
            return False
            
        with self._lock:
            try:
                shutil.rmtree(thread_path)
                return True
            except Exception as e:
                logger.error(f"Error al eliminar hilo {thread_id}: {e}")
                return False

    def rename_thread(self, thread_id: str, new_title: str) -> bool:
        """Renombra un hilo (tanto manual como automático)."""
        with self._lock:
            metadata = self.get_thread_metadata(thread_id)
            if not metadata:
                return False
                
            metadata["title"] = new_title
            metadata["has_generated_title"] = True
            metadata["updated_at"] = datetime.utcnow().isoformat()
            return self._save_metadata(thread_id, metadata)

    async def generate_title_if_needed(self, thread_id: str, messages: List[BaseMessage], llm_service) -> Optional[str]:
        """Genera un título con el LLM si hay al menos 2 mensajes (user+ai) y no tiene título."""
        with self._lock:
            metadata = self.get_thread_metadata(thread_id)
            if not metadata or metadata.get("has_generated_title"):
                return None
        
        # Filtrar mensajes de usuario con texto
        human_msgs = []
        for m in messages:
            if isinstance(m, HumanMessage) or (hasattr(m, "type") and m.type == "human"):
                content = m.content
                if isinstance(content, list):
                    text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                    content = " ".join(text_parts)
                if isinstance(content, str) and content.strip():
                    human_msgs.append(content.strip())

        # Filtrar mensajes de asistente con texto (evitando los que solo ejecutan herramientas o están vacíos)
        ai_msgs = []
        for m in messages:
            if isinstance(m, AIMessage) or (hasattr(m, "type") and m.type == "ai"):
                content = m.content
                if isinstance(content, list):
                    text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                    content = " ".join(text_parts)
                if isinstance(content, str) and content.strip():
                    ai_msgs.append(content.strip())
        
        if not human_msgs or not ai_msgs:
            return None
            
        prompt = (
            "Eres un asistente que debe generar un título conciso (máximo 5-6 palabras) "
            "para este hilo de conversación, basado en el siguiente intercambio inicial.\n\n"
            f"Usuario: {human_msgs[0][:300]}\n"
            f"Asistente: {ai_msgs[0][:300]}\n\n"
            "Solo responde con el título, sin comillas, markdown o explicaciones."
        )
        
        try:
            # Tratar de ejecutar de forma no bloqueante
            loop = asyncio.get_event_loop()
            
            def do_call():
                if hasattr(llm_service, "use_multi_provider") and llm_service.use_multi_provider and hasattr(llm_service, "provider_manager"):
                    # Extra args para kilocode
                    extra_args = {}
                    if "kilocode" in llm_service.model_name.lower():
                        extra_args["custom_llm_provider"] = "openai"

                    response_gen = llm_service.provider_manager.execute_with_fallback(
                        model_name=llm_service.model_name,
                        messages=[{"role": "user", "content": prompt}],
                        stream=False,
                        max_tokens=15,
                        temperature=0.3,
                        api_key=getattr(llm_service, "api_key", None),
                        api_base=getattr(llm_service, "api_base", None),
                        headers=getattr(llm_service, "headers", None),
                        **extra_args
                    )
                    response = next(response_gen)
                else:
                    from litellm import completion
                    api_key = getattr(llm_service, "api_key", None)
                    api_base = getattr(llm_service, "api_base", None)
                    kwargs = {
                        "model": llm_service.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 15,
                        "temperature": 0.3
                    }
                    if api_key: kwargs["api_key"] = api_key
                    if api_base: kwargs["api_base"] = api_base
                        
                    if "kilocode" in llm_service.model_name.lower() or (api_base and "kilo.ai" in api_base):
                        kwargs["custom_llm_provider"] = "openai"
                        
                    response = completion(**kwargs)
                    
                return response.choices[0].message.content.strip().strip('"\'')
                
            new_title = await loop.run_in_executor(None, do_call)
            
            if new_title:
                self.rename_thread(thread_id, new_title)
                return new_title
                
        except Exception as e:
            logger.error(f"Error generando título para hilo {thread_id}: {e}")
            
        return None
