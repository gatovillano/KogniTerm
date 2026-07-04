"""
KogniTerm Backend API — FastAPI app principal.

Canales disponibles:
  - WebSocket   /ws/{session_id}          → streaming bidireccional (principal)
  - SSE         /sse/{session_id}          → Server-Sent Events (clientes solo-lectura)
  - REST        POST /chat/{session_id}    → request/response síncrono
  - REST        GET  /sessions             → listar sesiones activas
  - REST        POST /sessions             → crear sesión nueva
  - REST        DELETE /sessions/{id}      → eliminar sesión
  - REST        POST /sessions/{id}/interrupt → interrumpir agente
  - REST        GET  /health              → health check

El agente permanece "despierto" entre mensajes: el historial de conversación,
el estado del grafo LangGraph y el contexto de herramientas se mantienen en
memoria por sesión hasta que la sesión es eliminada explícitamente.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, List, Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kogniterm.core.llm_service import LLMService
from kogniterm.server.session_pool import pool
from kogniterm.server.config import server_config, ChannelConfig
from kogniterm.server.channel_adapters import (
    WebhookAdapter,
    SlackAdapter,
    CLIAdapter,
    TelegramAdapter,
)

logger = logging.getLogger("kogniterm.server.app")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


# ── Modelos Pydantic ───────────────────────────────────────────────────────────


class MessageRequest(BaseModel):
    message: str = Field(..., description="Mensaje para el agente")
    session_id: Optional[str] = Field(
        default=None,
        description="ID de sesión existente. Si es None, se crea una nueva.",
    )


class LLMConfigRequest(BaseModel):
    model: Optional[str] = Field(default=None, description="Nombre del modelo LLM")
    api_key: Optional[str] = Field(default=None, description="API Key del proveedor")
    provider: Optional[str] = Field(default=None, description="Proveedor del modelo")


class SessionCreateRequest(BaseModel):
    session_id: Optional[str] = Field(
        default=None,
        description="ID personalizado. Si es None, se genera automáticamente.",
    )


class ThreadRenameRequest(BaseModel):
    title: str = Field(..., description="Nuevo título para el hilo")


class InterruptRequest(BaseModel):
    reason: Optional[str] = Field(default="Usuario solicitó interrupción.")


class CommandRequest(BaseModel):
    command: str


class CommandResponse(BaseModel):
    output: str
    error: str = ""
    exitCode: int = 0


class FileItem(BaseModel):
    name: str
    path: str
    isDirectory: bool
    size: Optional[int] = None


class DirectoryRequest(BaseModel):
    path: str = "."


class DirectoryResponse(BaseModel):
    items: List[FileItem]
    currentPath: str


class ChatMessageRequest(BaseModel):
    message: str
    workspace_id: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None


class SetConfigRequest(BaseModel):
    key: str
    value: Any
    scope: str = "project"  # "project" o "global"


class TelegramDetectRequest(BaseModel):
    token: str


# ── Lifespan ───────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa el LLMService y el SessionPool al arrancar el servidor."""
    logger.info("🚀 Iniciando KogniTerm Server...")
    loop = asyncio.get_event_loop()

    # Cargar LLMService en segundo plano para no colgar ni bloquear el inicio del servidor
    async def load_llm_service_background():
        logger.info(
            "⚙️  Cargando LLMService en segundo plano (evitando bloqueos en el arranque)..."
        )
        try:
            # Ejecutar el constructor síncrono de LLMService en un hilo del pool para no bloquear el loop principal
            llm_service = await loop.run_in_executor(None, LLMService)
            pool.initialize(llm_service=llm_service, loop=loop)
            logger.info("✅ KogniTerm Server y LLMService listos en segundo plano.")
        except Exception as e:
            logger.error(
                f"❌ Error crítico al inicializar LLMService en segundo plano: {e}"
            )

    asyncio.create_task(load_llm_service_background())

    # Inicializar canales externos configurados
    active_tasks = []
    for cfg in server_config.settings.channels:
        if cfg.enabled:
            logger.info(f"📡 Iniciando canal: {cfg.name} ({cfg.type})")

            if cfg.type in ("telegram", "telegram_bot"):
                token = cfg.params.get("token")
                if token:
                    adapter = TelegramAdapter(token=token, session_id=cfg.name)
                    task = asyncio.create_task(adapter.start())
                    active_tasks.append((adapter, task))
                else:
                    logger.warning(
                        f"⚠️ Canal Telegram '{cfg.name}' habilitado pero falta 'token' en params."
                    )

    logger.info("✅ KogniTerm Server listo.")
    yield

    logger.info("🛑 Cerrando KogniTerm Server...")
    # Detener canales activos
    for adapter, task in active_tasks:
        if hasattr(adapter, "stop"):
            await adapter.stop()
        task.cancel()

    pool._executor.shutdown(wait=False)


# ── Aplicación ─────────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    application = FastAPI(
        title="KogniTerm Backend API",
        description=(
            "API persistente multi-canal para KogniTerm. "
            "El agente permanece activo entre mensajes, manteniendo contexto y herramientas."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Health Check ────────────────────────────────────────────────────────────

    @application.get("/health", tags=["Sistema"])
    async def health():
        """Estado del servidor y sesiones activas."""
        sessions = pool.list_all()
        return {
            "status": "online",
            "active_sessions": len(sessions),
            "sessions": sessions,
            "configured_channels": [
                c.name for c in server_config.settings.channels if c.enabled
            ],
        }

    # ── Gestión de Configuración (Canales) ──────────────────────────────────────

    @application.get("/config/channels", tags=["Configuración"])
    async def list_configured_channels():
        """Lista todos los canales configurados (activos e inactivos)."""
        return {"channels": server_config.settings.channels}

    @application.post("/config/channels", tags=["Configuración"])
    async def add_or_update_channel(cfg: ChannelConfig):
        """Añade o actualiza la configuración de un canal."""
        server_config.add_channel(cfg)
        return {"status": "ok", "channel": cfg.name}

    @application.delete("/config/channels/{name}", tags=["Configuración"])
    async def remove_channel(name: str):
        """Elimina un canal de la configuración."""
        server_config.remove_channel(name)
        return {"status": "deleted", "channel": name}

    @application.patch("/config/channels/{name}/toggle", tags=["Configuración"])
    async def toggle_channel(name: str, enabled: bool):
        """Activa o desactiva un canal sin eliminarlo."""
        server_config.toggle_channel(name, enabled)
        return {"status": "updated", "channel": name, "enabled": enabled}

    # ── Gestión de Configuración (LLM) ──────────────────────────────────────

    @application.get("/api/models/available", tags=["Configuración"])
    @application.get("/models/available", tags=["Configuración"])
    async def get_available_models():
        """Devuelve la lista de modelos y proveedores disponibles, intentando obtenerlos dinámicamente si hay llaves/servicios configurados."""
        import httpx
        from kogniterm.terminal.config_manager import ConfigManager

        cm = ConfigManager()
        google_key = cm.get_api_key("google") or os.environ.get("GOOGLE_API_KEY")
        openai_key = cm.get_api_key("openai") or os.environ.get("OPENAI_API_KEY")
        openrouter_key = cm.get_api_key("openrouter") or os.environ.get(
            "OPENROUTER_API_KEY"
        )
        anthropic_key = cm.get_api_key("anthropic") or os.environ.get(
            "ANTHROPIC_API_KEY"
        )
        ollama_base = os.environ.get("OLLAMA_API_BASE") or "http://127.0.0.1:11434"

        # Valores por defecto de respaldo (fallback)
        google_models = [
            "gemini/gemini-1.5-flash",
            "gemini/gemini-1.5-pro",
            "gemini/gemini-2.0-flash-exp",
        ]
        openrouter_models = [
            "openrouter/google/gemini-2.0-flash-exp:free",
            "openrouter/openai/gpt-4o",
        ]
        openai_models = ["gpt-4o", "gpt-3.5-turbo"]
        anthropic_models = ["claude-3-5-sonnet-20240620", "claude-3-opus-20240229"]
        ollama_models = ["ollama/llama3", "ollama/mistral"]
        kilocode_models = ["kilocode/kilo/auto", "kilocode/openai/gpt-4o"]
        ollama_cloud_models = [
            "ollama_cloud/llama3:70b",
            "ollama_cloud/llama3:8b",
            "ollama_cloud/mistral",
            "ollama_cloud/mixtral",
            "ollama_cloud/codellama",
        ]
        antigravity_models = [
            "antigravity/gemini-3-flash",
            "antigravity/gemini-3-pro",
            "antigravity/gemini-2.5-flash",
            "antigravity/gemini-2.5-pro",
            "antigravity/gemini-1.5-pro",
            "antigravity/gemini-1.5-flash",
        ]

        async def fetch_google():
            nonlocal google_models
            if not google_key:
                return
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"https://generativelanguage.googleapis.com/v1beta/models?key={google_key}",
                        timeout=2.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = []
                        for m in data.get("models", []):
                            m_name = m.get("name", "")
                            if m_name.startswith("models/"):
                                m_name = m_name.replace("models/", "gemini/", 1)
                            if m_name and (
                                "gemini" in m_name or "text-embedding" in m_name
                            ):
                                fetched.append(m_name)
                        if fetched:
                            google_models = fetched
            except Exception:
                pass

        async def fetch_openrouter():
            nonlocal openrouter_models
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://openrouter.ai/api/v1/models", timeout=3.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = []
                        for m in data.get("data", []):
                            m_id = m.get("id")
                            if m_id:
                                fetched.append(f"openrouter/{m_id}")
                        if fetched:
                            openrouter_models = fetched
            except Exception:
                pass

        async def fetch_openai():
            nonlocal openai_models
            if not openai_key:
                return
            try:
                async with httpx.AsyncClient() as client:
                    headers = {"Authorization": f"Bearer {openai_key}"}
                    resp = await client.get(
                        "https://api.openai.com/v1/models", headers=headers, timeout=2.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = []
                        for m in data.get("data", []):
                            m_id = m.get("id")
                            if m_id and ("gpt" in m_id or "o1" in m_id or "o3" in m_id):
                                fetched.append(m_id)
                        if fetched:
                            openai_models = sorted(fetched)
            except Exception:
                pass

        async def fetch_anthropic():
            nonlocal anthropic_models
            if not anthropic_key:
                return
            try:
                async with httpx.AsyncClient() as client:
                    headers = {
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01",
                    }
                    resp = await client.get(
                        "https://api.anthropic.com/v1/models",
                        headers=headers,
                        timeout=2.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = []
                        for m in data.get("data", []):
                            m_id = m.get("id")
                            if m_id:
                                fetched.append(m_id)
                        if fetched:
                            anthropic_models = fetched
            except Exception:
                pass

        async def fetch_ollama():
            nonlocal ollama_models
            try:
                base = ollama_base.rstrip("/")
                if base.endswith("/v1"):
                    base = base[:-3]
                if base.endswith("/api"):
                    base = base[:-4]
                base = base.rstrip("/")
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{base}/api/tags", timeout=1.5)
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = []
                        for m in data.get("models", []):
                            m_name = m.get("name")
                            if m_name:
                                if m_name.startswith("ollama/"):
                                    fetched.append(m_name)
                                else:
                                    fetched.append(f"ollama/{m_name}")
                        if fetched:
                            ollama_models = fetched
            except Exception:
                pass

        async def fetch_kilocode():
            nonlocal kilocode_models
            kilocode_key = cm.get_api_key("kilocode") or os.environ.get(
                "KILOCODE_API_KEY"
            )
            if not kilocode_key:
                return
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://api.kilo.ai/api/gateway/models",
                        headers={"Authorization": f"Bearer {kilocode_key}"},
                        timeout=3.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = []
                        model_list = (
                            data
                            if isinstance(data, list)
                            else data.get("models", data.get("data", []))
                        )
                        for m in model_list:
                            model_id = m.get("id", m.get("model", ""))
                            if model_id:
                                if not model_id.startswith("kilocode/"):
                                    model_id = f"kilocode/{model_id}"
                                fetched.append(model_id)
                        if fetched:
                            kilocode_models = fetched
            except Exception:
                pass

        async def fetch_ollama_cloud():
            nonlocal ollama_cloud_models
            ollama_cloud_key = cm.get_api_key("ollama_cloud") or os.environ.get("OLLAMA_CLOUD_API_KEY")
            ollama_cloud_base = os.environ.get("OLLAMA_CLOUD_API_BASE") or "https://ollama.com/v1"
            if not ollama_cloud_key:
                return
            try:
                async with httpx.AsyncClient() as client:
                    headers = {"Authorization": f"Bearer {ollama_cloud_key}"}
                    resp = await client.get(f"{ollama_cloud_base}/models", headers=headers, timeout=2.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        fetched = []
                        model_list = data if isinstance(data, list) else data.get("data", data.get("models", []))
                        for m in model_list:
                            m_id = m.get("id", m.get("name", ""))
                            if m_id:
                                if not m_id.startswith("ollama_cloud/"):
                                    m_id = f"ollama_cloud/{m_id}"
                                fetched.append(m_id)
                        if fetched:
                            ollama_cloud_models = fetched
            except Exception:
                pass

        async def fetch_antigravity():
            nonlocal antigravity_models
            try:
                from kogniterm.core.antigravity_client import AntigravityClient
                loop = asyncio.get_event_loop()
                models_tuples = await loop.run_in_executor(
                    None, AntigravityClient.fetch_available_models
                )
                if models_tuples:
                    fetched = []
                    for model_id, label in models_tuples:
                        if not model_id.startswith("antigravity/"):
                            model_id = f"antigravity/{model_id}"
                        fetched.append(model_id)
                    if fetched:
                        antigravity_models = fetched
            except Exception:
                pass

        # Ejecutar todas las consultas en paralelo
        await asyncio.gather(
            fetch_google(),
            fetch_openrouter(),
            fetch_openai(),
            fetch_anthropic(),
            fetch_ollama(),
            fetch_kilocode(),
            fetch_ollama_cloud(),
            fetch_antigravity(),
            return_exceptions=True,
        )

        return {
            "providers": [
                {"id": "google", "name": "Google AI Studio", "models": google_models},
                {"id": "openrouter", "name": "OpenRouter", "models": openrouter_models},
                {"id": "openai", "name": "OpenAI", "models": openai_models},
                {"id": "anthropic", "name": "Anthropic", "models": anthropic_models},
                {"id": "ollama", "name": "Ollama Local", "models": ollama_models},
                {"id": "ollama_cloud", "name": "Ollama Cloud", "models": ollama_cloud_models},
                {"id": "antigravity", "name": "Google Antigravity", "models": antigravity_models},
                {
                    "id": "kilocode",
                    "name": "KiloCode Gateway",
                    "models": kilocode_models,
                },
            ]
        }

    @application.get("/api/config/llm", tags=["Configuración"])
    @application.get("/config/llm", tags=["Configuración"])
    async def get_llm_config():
        """Obtiene la configuración actual del LLM (enmascarando keys)."""
        from kogniterm.terminal.config_manager import ConfigManager

        cm = ConfigManager()

        model = cm.get_config("default_model") or os.environ.get(
            "LITELLM_MODEL", "google/gemini-1.5-flash"
        )

        # Detectar proveedor basado en el modelo
        provider = "google"
        model_lower = model.lower()
        if "openrouter" in model_lower:
            provider = "openrouter"
        elif "gpt" in model_lower or "openai" in model_lower:
            provider = "openai"
        elif "claude" in model_lower or "anthropic" in model_lower:
            provider = "anthropic"
        elif "ollama" in model_lower:
            provider = "ollama"
        elif "kilocode" in model_lower:
            provider = "kilocode"

        raw_key = cm.get_api_key(provider) or ""
        masked_key = (
            f"{raw_key[:4]}...{raw_key[-4:]}" if len(raw_key) > 8 else "********"
        )

        return {
            "provider": provider,
            "model": model,
            "api_key_masked": masked_key,
            "has_key": bool(raw_key),
            "reasoning_effort": cm.get_config("reasoning_effort") or "medium",
        }

    @application.post("/api/config/llm", tags=["Configuración"])
    @application.post("/config/llm", tags=["Configuración"])
    async def update_llm_config(req: LLMConfigRequest):
        """Actualiza el modelo y la API key del LLM en el ConfigManager."""
        from kogniterm.terminal.config_manager import ConfigManager

        cm = ConfigManager()

        # Guardar el modelo por defecto si se proporcionó, o si se especificó un proveedor
        if req.model:
            cm.set_project_config("default_model", req.model)
        elif req.provider:
            default_models = {
                "google": "google/gemini-1.5-flash",
                "openai": "openai/gpt-4o",
                "anthropic": "anthropic/claude-3-5-sonnet-20240620",
                "openrouter": "openrouter/google/gemini-2.5-flash",
                "ollama": "ollama/llama3",
                "kilocode": "kilocode/kilo/auto",
                "litellm": "google/gemini-1.5-flash",
            }
            new_model = default_models.get(req.provider.lower())
            if new_model:
                cm.set_project_config("default_model", new_model)

        # Guardar la API key si se proporcionó
        if req.api_key:
            # Intentar inferir el proveedor si no viene explícitamente
            provider = req.provider
            if not provider:
                # Mapeo simple basado en el nombre del modelo
                target_model = req.model or cm.get_config("default_model") or ""
                model_lower = target_model.lower()
                if "gemini" in model_lower or "google" in model_lower:
                    provider = "google"
                elif "openai" in model_lower or "gpt" in model_lower:
                    provider = "openai"
                elif "anthropic" in model_lower or "claude" in model_lower:
                    provider = "anthropic"
                elif "openrouter" in model_lower:
                    provider = "openrouter"
                elif "ollama" in model_lower:
                    provider = "ollama_cloud"
                elif "kilocode" in model_lower:
                    provider = "kilocode"
                else:
                    provider = "litellm"  # Fallback genérico

            cm.set_api_key(provider, req.api_key)

        # Recargar la configuración en el LLMService del pool si ya existe
        if pool._llm_service:
            pool._llm_service.reload_config()

        return {
            "status": "ok",
            "model": req.model,
            "provider": req.provider or "inferred/ignored",
        }

    # ── Gestión de Configuración (Adicionales) ──────────────────────────────

    @application.get("/api/config/all", tags=["Configuración"])
    async def get_all_config():
        """Obtiene la configuración global, de proyecto y combinada."""
        from kogniterm.terminal.config_manager import ConfigManager
        cm = ConfigManager()
        global_conf = cm.load_global_config()
        project_conf = cm.load_project_config()
        merged_conf = cm.get_all_config()
        
        def mask_dict(d):
            res = {}
            for k, v in d.items():
                if any(s in k.lower() for s in ("key", "token", "secret")):
                    if v and len(str(v)) > 8:
                        res[k] = f"{str(v)[:4]}...{str(v)[-4:]}"
                    elif v:
                        res[k] = "********"
                    else:
                        res[k] = ""
                else:
                    res[k] = v
            return res
            
        return {
            "global": mask_dict(global_conf),
            "project": mask_dict(project_conf),
            "merged": mask_dict(merged_conf),
            "has_keys": {
                k: bool(v) for k, v in merged_conf.items() if any(s in k.lower() for s in ("key", "token", "secret"))
            }
        }

    @application.post("/api/config/set", tags=["Configuración"])
    async def set_config_value(req: SetConfigRequest = Body(...)):
        """Establece una variable de configuración en ámbito global o proyecto."""
        from kogniterm.terminal.config_manager import ConfigManager
        cm = ConfigManager()
        
        if req.scope == "global":
            cm.set_global_config(req.key, req.value)
        else:
            cm.set_project_config(req.key, req.value)
            
        # Si cambia algo del LLM o modelo por defecto, recargar el servicio en el pool
        if req.key in ("default_model", "reasoning_effort") or req.key.startswith("api_key_"):
            if pool._llm_service:
                pool._llm_service.reload_config()
                
        return {"status": "ok", "key": req.key, "scope": req.scope}

    @application.post("/api/config/telegram/detect-chat-id", tags=["Configuración"])
    async def detect_telegram_chat_id(req: TelegramDetectRequest):
        """Busca el primer chat_id privado que interactúa con el bot en un timeout corto."""
        from kogniterm.terminal.telegram_chatid_helper import get_first_private_chat_id
        # Hacemos una llamada rápida con timeout de 15 segundos
        loop = asyncio.get_event_loop()
        chat_id = await loop.run_in_executor(
            None, get_first_private_chat_id, req.token, 15
        )
        return {"chat_id": chat_id}

    @application.get("/api/skills", tags=["Skills"])
    async def get_skills():
        """Lista todas las skills registradas clasificadas por su ámbito."""
        await pool.wait_until_ready()
        if not pool._llm_service or not pool._llm_service.skill_manager:
            return {"skills": []}
            
        sm = pool._llm_service.skill_manager
        try:
            sm.discover_all_skills()
        except Exception as e:
            logger.error(f"Error descubriendo skills: {e}")
            
        result = []
        for name, skill in sm.skills.items():
            path_str = str(skill.path.resolve())
            
            # bundled (por defecto)
            if hasattr(sm, 'bundled_path') and sm.bundled_path and (path_str.startswith(str(sm.bundled_path.resolve())) or (hasattr(sm, 'legacy_bundled_path') and sm.legacy_bundled_path and path_str.startswith(str(sm.legacy_bundled_path.resolve())))):
                scope = "default"
            # managed (creadas por el agente)
            elif hasattr(sm, 'managed_path') and sm.managed_path and path_str.startswith(str(sm.managed_path.resolve())):
                scope = "agent"
            # global (globales)
            elif (hasattr(sm, 'global_skills_path') and sm.global_skills_path and path_str.startswith(str(sm.global_skills_path.resolve()))) or (hasattr(sm, 'user_skills_path') and sm.user_skills_path and path_str.startswith(str(sm.user_skills_path.resolve()))):
                scope = "global"
            # workspace (del proyecto)
            elif (hasattr(sm, 'workspace_path') and sm.workspace_path and path_str.startswith(str(sm.workspace_path.resolve()))) or (hasattr(sm, 'legacy_workspace_path') and sm.legacy_workspace_path and path_str.startswith(str(sm.legacy_workspace_path.resolve()))):
                scope = "workspace"
            else:
                scope = "external"
                
            tools = []
            for tool in skill.tools:
                tools.append({
                    "name": getattr(tool, 'name', tool.__class__.__name__),
                    "description": getattr(tool, 'description', '')
                })
                
            result.append({
                "name": skill.name,
                "version": skill.version,
                "author": skill.author,
                "description": skill.description,
                "category": skill.category,
                "scope": scope,
                "path": path_str,
                "security_level": skill.security_level,
                "tags": skill.tags,
                "dependencies": skill.dependencies,
                "tools": tools,
                "loaded": skill.loaded
            })
            
        return {"skills": result}

    # ── Utilidades Desktop (Ejecución y Archivos) ─────────────────────────────

    @application.get("/api/workspace/status", tags=["Desktop"])
    async def workspace_status():
        """Obtiene el estado del workspace (indexación, etc)."""
        try:
            # Esperar a que el pool y el LLMService estén listos para evitar colisiones en ChromaDB al arranque
            await pool.wait_until_ready()

            if pool._llm_service and pool._llm_service.vector_db_manager:
                indexed = pool._llm_service.vector_db_manager.is_indexed()
            else:
                indexed = False

            return {"indexed": indexed, "path": os.getcwd()}
        except Exception as e:
            return {"indexed": False, "error": str(e), "path": os.getcwd()}

    @application.post("/api/workspace/index", tags=["Desktop"])
    async def trigger_indexing(session_id: Optional[str] = None):
        """Inicia el proceso de indexación del codebase en segundo plano."""
        asyncio.create_task(run_indexing_task(session_id))
        return {"status": "started", "message": "Indexación iniciada en segundo plano."}

    async def run_indexing_task(session_id: Optional[str] = None):
        """Tarea de fondo para indexar el codebase."""
        project_path = os.getcwd()
        try:
            from kogniterm.core.context.codebase_indexer import CodebaseIndexer
            from kogniterm.core.context.vector_db_manager import VectorDBManager

            # Helper para enviar progreso si hay una sesión asociada
            def progress_callback(current, total, description):
                if session_id:
                    s = pool.get(session_id)
                    if s:
                        s.ui._push(
                            "indexing_progress",
                            {
                                "current": current,
                                "total": total,
                                "description": description,
                                "percentage": int((current / total) * 100)
                                if total > 0
                                else 0,
                            },
                        )

            indexer = CodebaseIndexer(project_path)
            chunks = await indexer.index_project(
                project_path, show_progress=False, progress_callback=progress_callback
            )

            if chunks:
                if pool._llm_service and pool._llm_service.vector_db_manager:
                    vdb = pool._llm_service.vector_db_manager
                    vdb.clear_collection()
                    vdb.add_chunks(chunks)
                else:
                    vdb = VectorDBManager(project_path)
                    vdb.clear_collection()
                    vdb.add_chunks(chunks)
                    vdb.close()

                if session_id:
                    s = pool.get(session_id)
                    if s:
                        s.ui._push("indexing_complete", {"chunks": len(chunks)})
            else:
                if session_id:
                    s = pool.get(session_id)
                    if s:
                        s.ui._push("indexing_complete", {"chunks": 0})

        except Exception as e:
            logger.error(f"Error en tarea de indexación: {e}")
            if session_id:
                s = pool.get(session_id)
                if s:
                    s.ui._push("indexing_error", {"message": str(e)})

    @application.post("/api/execute", response_model=CommandResponse, tags=["Desktop"])
    async def execute_command(request: CommandRequest):
        """Ejecuta un comando y devuelve la salida."""
        try:
            if not request.command or not request.command.strip():
                return CommandResponse(output="", error="Empty command", exitCode=1)

            args = shlex.split(request.command, posix=True)
            if not args:
                return CommandResponse(output="", error="Empty command", exitCode=1)

            process = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return CommandResponse(
                output=stdout.decode("utf-8") if stdout else "",
                error=stderr.decode("utf-8") if stderr else "",
                exitCode=process.returncode or 0,
            )
        except Exception as e:
            return CommandResponse(output="", error=str(e), exitCode=1)

    @application.post(
        "/api/files/list", response_model=DirectoryResponse, tags=["Desktop"]
    )
    async def list_directory(request: DirectoryRequest):
        """Lista el contenido de un directorio."""
        try:
            path = os.path.abspath(request.path)
            items = []
            for entry in os.scandir(path):
                if entry.name.startswith("."):
                    continue
                item = FileItem(
                    name=entry.name,
                    path=entry.path,
                    isDirectory=entry.is_dir(),
                    size=entry.stat().st_size if entry.is_file() else None,
                )
                items.append(item)
            items.sort(key=lambda x: (not x.isDirectory, x.name.lower()))
            return DirectoryResponse(items=items, currentPath=path)
        except Exception as e:
            return DirectoryResponse(items=[], currentPath=request.path)

    # ── Gestión de sesiones ─────────────────────────────────────────────────────

    @application.get("/sessions", tags=["Sesiones"])
    async def list_sessions():
        """Lista todas las sesiones activas con su estado."""
        await pool.wait_until_ready()
        return {"sessions": pool.list_all()}

    @application.post("/sessions", tags=["Sesiones"], status_code=201)
    async def create_session(req: SessionCreateRequest = SessionCreateRequest()):
        """Crea una nueva sesión de agente y la mantiene en memoria."""
        await pool.wait_until_ready()
        sid = req.session_id or pool.new_session_id()
        session = pool.get_or_create(sid)
        return {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
        }

    @application.delete("/sessions/{session_id}", tags=["Sesiones"])
    async def delete_session(session_id: str):
        """Elimina una sesión y libera su memoria."""
        await pool.wait_until_ready()
        deleted = pool.delete(session_id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail=f"Sesión '{session_id}' no encontrada."
            )
        return {"deleted": session_id}

    @application.post("/api/sessions/{session_id}/close", tags=["Sesiones"])
    async def close_session(session_id: str):
        """Notifica que una sesión ha finalizado (ej. TUI cerrada)."""
        await pool.wait_until_ready()
        session = pool.get(session_id)
        if session:
            # Forzar guardado final por seguridad
            if session.thread_manager:
                session.thread_manager.save_thread_messages(
                    session_id, session.agent_state.messages
                )
            logger.info(f"[Server] Sesión {session_id} cerrada correctamente.")
            return {"status": "closed", "session_id": session_id}
        return {"status": "not_found", "session_id": session_id}

    # ── Gestión de Hilos de Chat (Threads) ─────────────────────────────────────

    @application.get("/api/threads", tags=["Threads"])
    async def list_threads():
        """Lista todos los hilos guardados."""
        await pool.wait_until_ready()
        if pool._thread_manager:
            return {"threads": pool._thread_manager.list_threads()}
        return {"threads": []}

    @application.post("/api/threads", tags=["Threads"], status_code=201)
    async def create_thread(req: SessionCreateRequest = SessionCreateRequest()):
        """Crea un hilo nuevo vacío."""
        await pool.wait_until_ready()
        sid = req.session_id or pool.new_session_id()
        if pool._thread_manager:
            metadata = pool._thread_manager.create_thread(thread_id=sid)
            return {"thread_id": sid, "metadata": metadata}
        return {"error": "ThreadManager no disponible"}

    @application.delete("/api/threads/{thread_id}", tags=["Threads"])
    async def delete_thread(thread_id: str):
        """Elimina un hilo de chat."""
        await pool.wait_until_ready()
        if pool._thread_manager:
            success = pool._thread_manager.delete_thread(thread_id)
            if success:
                # Si estaba en memoria, quitarlo
                pool.delete(thread_id)
                return {"deleted": thread_id}
        raise HTTPException(
            status_code=404, detail="Hilo no encontrado o error al eliminar"
        )

    @application.patch("/api/threads/{thread_id}", tags=["Threads"])
    async def rename_thread(thread_id: str, req: ThreadRenameRequest):
        """Renombra manualmente un hilo de chat."""
        await pool.wait_until_ready()
        if pool._thread_manager:
            success = pool._thread_manager.rename_thread(thread_id, req.title)
            if success:
                return {"status": "ok", "thread_id": thread_id, "title": req.title}
        raise HTTPException(status_code=404, detail="Hilo no encontrado")

    def message_to_frontend_dict(msg, index: int) -> dict:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
        from datetime import datetime
        
        role = "system"
        if isinstance(msg, HumanMessage) or (hasattr(msg, "type") and msg.type == "human"):
            role = "user"
        elif isinstance(msg, AIMessage) or (hasattr(msg, "type") and msg.type == "ai"):
            role = "assistant"
        elif isinstance(msg, SystemMessage) or (hasattr(msg, "type") and msg.type == "system"):
            role = "system"
        elif isinstance(msg, ToolMessage) or (hasattr(msg, "type") and msg.type == "tool"):
            role = "tool"
            
        content = msg.content if msg.content is not None else ""
        if isinstance(content, list):
            text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
            content = " ".join(text_parts)
            
        reasoning = ""
        tool_calls = []
        tool_call_id = None
        
        # Extraer tool_calls si es AIMessage
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.get("id") or str(index),
                    "name": tc.get("name") or "Unknown Tool",
                    "args": tc.get("args") or {}
                })
                
        # Extraer tool_call_id si es ToolMessage
        if hasattr(msg, "tool_call_id") and msg.tool_call_id:
            tool_call_id = msg.tool_call_id
            
        # Buscar razonamiento en additional_kwargs
        if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
            reasoning = msg.additional_kwargs.get("reasoning_content") or msg.additional_kwargs.get("thought") or ""
            
        return {
            "id": f"loaded-{index}",
            "role": role,
            "content": content,
            "reasoning": reasoning,
            "tool_calls": tool_calls,
            "tool_call_id": tool_call_id,
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }

    @application.get("/api/threads/{thread_id}/messages", tags=["Threads"])
    async def get_thread_messages(thread_id: str):
        """Obtiene los mensajes de un hilo de chat en formato compatible con el frontend."""
        await pool.wait_until_ready()
        if pool._thread_manager:
            messages = pool._thread_manager.load_thread_messages(thread_id)
            if messages is not None:
                frontend_messages = []
                for i, msg in enumerate(messages):
                    frontend_messages.append(message_to_frontend_dict(msg, i))
                return {"messages": frontend_messages}
        return {"messages": []}

    @application.post("/api/chat/message", tags=["Chat"])
    async def chat_message_compat(req: ChatMessageRequest):
        """Endpoint compatible con la aplicación desktop (simplified chat)."""
        await pool.wait_until_ready()
        session_id = req.session_id or f"rest-{uuid.uuid4().hex[:8]}"
        session = pool.get_or_create(session_id)

        if session.is_running:
            raise HTTPException(status_code=409, detail="El agente ya está procesando.")

        # Recolectar respuesta completa
        collected: list = []
        done_event = asyncio.Event()

        async def collector():
            async for event in session.ui.events():
                collected.append(event)
                if event["type"] in ("done", "error"):
                    done_event.set()
                    break

        collect_task = asyncio.create_task(collector())
        await session.send(req.message, pool._executor)
        done_event.set()
        await asyncio.sleep(0.1)
        collect_task.cancel()

        text_chunks = [e["data"] for e in collected if e["type"] == "chunk"]
        # A veces el data es un dict con content
        text_content = []
        for d in text_chunks:
            if isinstance(d, dict):
                text_content.append(d.get("content", ""))
            else:
                text_content.append(str(d))

        full_text = "".join(text_content)
        return {"response": full_text}

    # ── Canal REST (síncrono, para integraciones simples) ──────────────────────

    @application.post("/chat/{session_id}", tags=["Chat"])
    async def chat_rest(session_id: str, req: MessageRequest):
        """
        Envía un mensaje y espera la respuesta completa (bloqueante).
        Útil para bots/CLI que no soportan streaming.
        """
        await pool.wait_until_ready()
        session = pool.get_or_create(session_id)
        if session.is_running:
            raise HTTPException(
                status_code=409,
                detail="El agente ya está procesando un mensaje en esta sesión.",
            )

        # Cola temporal para recolectar todos los eventos de esta invocación
        collected: list = []
        done_event = asyncio.Event()

        async def collector():
            async for event in session.ui.events():
                collected.append(event)
                if event["type"] in ("done", "error"):
                    done_event.set()
                    break

        collect_task = asyncio.create_task(collector())
        await session.send(req.message, pool._executor)
        done_event.set()  # Asegurar que collector termine
        await asyncio.sleep(0.1)
        collect_task.cancel()

        # Extraer texto de respuesta del AI desde los eventos
        text_chunks = [e["data"] for e in collected if e["type"] == "stream"]
        full_text = "".join(text_chunks)

        return {
            "session_id": session_id,
            "response": full_text,
            "events": collected,
        }

    # ── Canal SSE (Server-Sent Events) para clientes solo-lectura ─────────────

    @application.get("/sse/{session_id}", tags=["Chat"])
    async def chat_sse(session_id: str, message: str):
        """
        Envía un mensaje y recibe la respuesta como Server-Sent Events.
        Ideal para integraciones web unidireccionales.

        Parámetro: ?message=<texto>
        """
        await pool.wait_until_ready()
        session = pool.get_or_create(session_id)

        async def event_generator() -> AsyncIterator[str]:
            send_task = asyncio.create_task(session.send(message, pool._executor))

            async for event in session.ui.events():
                # Formato SSE: "data: <json>\n\n"
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event["type"] in ("done", "error"):
                    break

            await asyncio.sleep(0)  # Ceder el loop
            send_task.cancel()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Canal WebSocket (bidireccional, streaming completo) ───────────────────

    @application.websocket("/ws/chat")
    async def websocket_chat_compat(websocket: WebSocket):
        """Crea una sesión nueva única por cada conexión desktop."""
        unique_id = f"desktop-{uuid.uuid4().hex[:8]}"
        await websocket_chat(websocket, unique_id)

    @application.websocket("/ws/{session_id}")
    async def websocket_chat(websocket: WebSocket, session_id: str):
        """
        Canal WebSocket bidireccional.

        Protocolo de mensajes cliente → servidor (JSON):
          {"type": "message",    "text": "..."}    → enviar mensaje al agente
          {"type": "interrupt"}                    → interrumpir ejecución actual
          {"type": "ping"}                         → keep-alive

        Protocolo servidor → cliente (JSON):
          {"type": "stream",       "data": "...", "ts": "..."}  → chunk de texto
          {"type": "tool_start",   "data": {...}, "ts": "..."}  → inicio de herramienta
          {"type": "tool_output",  "data": {...}, "ts": "..."}  → salida de herramienta
          {"type": "live_update",  "data": "...", "ts": "..."}  → actualización visual
          {"type": "task_tracker", "data": {...}, "ts": "..."}  → progreso de tareas
          {"type": "message",      "data": {...}, "ts": "..."}  → mensaje del agente
          {"type": "done",         "data": {...}, "ts": "..."}  → fin de ciclo
          {"type": "error",        "data": {...}, "ts": "..."}  → error
          {"type": "pong",         "data": {},    "ts": "..."}  → respuesta keep-alive
        """
        await websocket.accept()

        await pool.wait_until_ready()

        # Reconocer cuando una sesión es nueva o existente
        is_new = session_id not in pool._sessions
        session = pool.get_or_create(session_id)

        logger.info(
            f"[WS] Cliente conectado a sesión {session_id} ({'NUEVA' if is_new else 'EXISTENTE'})"
        )

        from kogniterm.terminal.config_manager import ConfigManager

        cm = ConfigManager()
        current_config = {
            "model": cm.get_config("default_model")
            or os.environ.get("LITELLM_MODEL", "google/gemini-1.5-flash"),
        }

        # Tarea A: relay de eventos del agente → cliente WS
        async def relay_events():
            try:
                async for event in session.ui.events():
                    await websocket.send_json(event)
            except WebSocketDisconnect:
                logger.info(f"[WS:{session_id}] relay_events: cliente desconectado")
            except Exception as exc:
                logger.warning(f"[WS:{session_id}] relay_events terminado: {exc}")

        relay_task = asyncio.create_task(relay_events())

        # Tarea B: enviar estado inicial y recibir mensajes del cliente
        try:
            # Enviar estado inicial con configuración y metadatos de persistencia
            await websocket.send_json(
                {
                    "type": "connected",
                    "data": {
                        **session.to_dict(),
                        "config": current_config,
                        "is_new": is_new,
                        "persistent": True,
                    },
                }
            )
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json(
                        {"type": "error", "data": "JSON inválido."}
                    )
                    continue

                msg_type = data.get("type", "message")

                if msg_type == "message":
                    text = data.get("text", "").strip()
                    if not text:
                        continue
                    asyncio.create_task(session.send(text, pool._executor))

                elif msg_type == "interrupt":
                    session.interrupt()
                    await websocket.send_json(
                        {"type": "info", "data": "Interrupción enviada."}
                    )

                elif msg_type == "start_indexing":
                    asyncio.create_task(run_indexing_task(session_id))
                    await websocket.send_json(
                        {"type": "info", "data": "Indexación iniciada."}
                    )

                elif msg_type == "approval_response":
                    request_id = data.get("id")
                    approved = data.get("approved", False)
                    if request_id:
                        session.ui.handle_approval_response(request_id, approved)
                        await websocket.send_json(
                            {
                                "type": "info",
                                "data": f"Aprobación procesada para {request_id}.",
                            }
                        )
                    else:
                        await websocket.send_json(
                            {"type": "error", "data": "Falta ID de aprobación."}
                        )

                elif msg_type == "terminal_input":
                    text = data.get("text", "")
                    if text:
                        session.write_terminal_input(text)

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong", "data": {}})

                else:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "data": f"Tipo de mensaje desconocido: {msg_type}",
                        }
                    )

        except WebSocketDisconnect:
            logger.info(f"[WS] Cliente desconectado de sesión {session_id}")
        except Exception as exc:
            logger.error(f"[WS:{session_id}] Error inesperado: {exc}")
        finally:
            relay_task.cancel()
            try:
                await relay_task
            except asyncio.CancelledError:
                pass

    return application


app = create_app()


# ── Entry point ────────────────────────────────────────────────────────────────


def run_server(host: str = "0.0.0.0", port: int = 8765, reload: bool = False):
    """Lanza el servidor KogniTerm."""
    uvicorn.run(
        "kogniterm.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
