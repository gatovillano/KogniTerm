import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("kogniterm.server.config")

class ChannelConfig(BaseModel):
    name: str
    type: str  # 'slack', 'telegram', 'discord', 'webhook', 'cli'
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)

import uuid

class HeartbeatConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Nombre descriptivo del heartbeat")
    prompt: str = Field(..., description="Prompt a ejecutar periódicamente")
    interval_seconds: int = Field(default=300, ge=5, description="Frecuencia de ejecución en segundos")
    enabled: bool = Field(default=True, description="Estado activo del heartbeat")
    session_id: Optional[str] = Field(default=None, description="ID de sesión objetivo. Si es None, se usa un ID por defecto.")
    last_run: Optional[str] = Field(default=None, description="Fecha/hora ISO del último ciclo ejecutado")
    last_status: Optional[str] = Field(default=None, description="Resultado de la última ejecución (success/error)")
    last_error: Optional[str] = Field(default=None, description="Detalle del último error si ocurrió")

class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8765
    channels: List[ChannelConfig] = [
        ChannelConfig(name="cli_local", type="cli", enabled=False),
        ChannelConfig(name="webhook_default", type="webhook", enabled=False, params={"url": "http://localhost:5000/hook"}),
        ChannelConfig(name="telegram_bot_default", type="telegram_bot", enabled=False, params={"token": "YOUR_TELEGRAM_BOT_TOKEN"})
    ]
    heartbeats: List[HeartbeatConfig] = []

class ServerConfigManager:
    """
    Manages the server-specific configuration, allowing dynamic channel management.
    """
    CONFIG_FILE = Path(os.getenv("KOGNITERM_SERVER_CONFIG_FILE", str(Path.home() / ".kogniterm" / "server_config.json")))

    def __init__(self):
        self.settings = self.load_config()

    def load_config(self) -> ServerSettings:
        if not self.CONFIG_FILE.exists():
            # Create default config if not exists
            settings = ServerSettings()
            self.save_config(settings)
            return settings
        
        try:
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return ServerSettings(**data)
        except Exception as e:
            logger.error(f"Error loading server config: {e}")
            return ServerSettings()

    def save_config(self, settings: ServerSettings):
        self.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings.model_dump(), f, indent=4)

    def upsert_channel(self, channel: ChannelConfig):
        for index, existing in enumerate(self.settings.channels):
            if existing.name == channel.name:
                self.settings.channels[index] = channel
                self.save_config(self.settings)
                return

        self.settings.channels.append(channel)
        self.save_config(self.settings)

    def add_channel(self, channel: ChannelConfig):
        self.upsert_channel(channel)

    def remove_channel(self, channel_name: str):
        self.settings.channels = [c for c in self.settings.channels if c.name != channel_name]
        self.save_config(self.settings)

    def toggle_channel(self, channel_name: str, enabled: bool):
        for c in self.settings.channels:
            if c.name == channel_name:
                c.enabled = enabled
                break
        self.save_config(self.settings)

    def upsert_heartbeat(self, heartbeat: HeartbeatConfig):
        for index, existing in enumerate(self.settings.heartbeats):
            if existing.id == heartbeat.id:
                self.settings.heartbeats[index] = heartbeat
                self.save_config(self.settings)
                return

        self.settings.heartbeats.append(heartbeat)
        self.save_config(self.settings)

    def add_heartbeat(self, heartbeat: HeartbeatConfig):
        self.upsert_heartbeat(heartbeat)

    def remove_heartbeat(self, heartbeat_id: str):
        self.settings.heartbeats = [hb for hb in self.settings.heartbeats if hb.id != heartbeat_id]
        self.save_config(self.settings)

    def toggle_heartbeat(self, heartbeat_id: str, enabled: bool):
        for hb in self.settings.heartbeats:
            if hb.id == heartbeat_id:
                hb.enabled = enabled
                break
        self.save_config(self.settings)

    def update_heartbeat_status(self, heartbeat_id: str, status: str, error: Optional[str] = None, run_time: Optional[str] = None):
        for hb in self.settings.heartbeats:
            if hb.id == heartbeat_id:
                hb.last_status = status
                hb.last_error = error
                hb.last_run = run_time
                break
        self.save_config(self.settings)

server_config = ServerConfigManager()
