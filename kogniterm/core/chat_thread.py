"""
ChatThread: modelo de datos y serialización para hilos de chat persistentes.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

from langchain_core.messages import BaseMessage, messages_to_dict, messages_from_dict


@dataclass
class ChatThread:
    """Modelo de datos de un hilo de chat persistente."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Nueva conversación"
    title_source: str = "manual"  # "llm" | "fallback" | "manual"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    parent_thread_id: Optional[str] = None
    messages: List[BaseMessage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa el hilo a un diccionario JSON-compatible."""
        data = asdict(self)
        data["messages"] = messages_to_dict(self.messages)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatThread":
        """Crea un ChatThread desde un diccionario."""
        raw = dict(data)
        messages = messages_from_dict(raw.pop("messages", []) or [])
        return cls(messages=messages, **raw)

    def touch(self) -> None:
        """Actualiza la fecha de modificación."""
        self.updated_at = datetime.utcnow().isoformat()

    def with_title(self, title: str, source: str = "manual") -> "ChatThread":
        """Devuelve una copia del hilo con el título actualizado."""
        updated = ChatThread(
            id=self.id,
            title=title,
            title_source=source,
            created_at=self.created_at,
            updated_at=datetime.utcnow().isoformat(),
            parent_thread_id=self.parent_thread_id,
            messages=list(self.messages),
            metadata=dict(self.metadata),
        )
        return updated

    def summary(self) -> Dict[str, Any]:
        """Resumen ligero para listados."""
        return {
            "id": self.id,
            "title": self.title,
            "title_source": self.title_source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parent_thread_id": self.parent_thread_id,
            "message_count": len(self.messages),
            "metadata": self.metadata,
        }
