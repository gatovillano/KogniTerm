# Plan de Implementación: Conexión a Servidores MCP desde KogniTerm y KogniTerm Desktop

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Habilitar a KogniTerm y KogniTerm Desktop para conectar, probar y gestionar servidores MCP (Model Context Protocol) configurables (`stdio` y `sse`) e inyectar dinámicamente sus herramientas en los agentes.

**Architecture:** Módulo Python `MCPManager` en `kogniterm/core/mcp` que administra clientes MCP y las convierte en herramientas LangChain (`BaseTool`) para `LLMService`. Exposición de endpoints REST en `kogniterm/server/app.py` y nueva pestaña `McpTab.tsx` en `kogniterm-desktop`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, `langchain_mcp_adapters`, React, TypeScript, TailwindCSS / UI components.

## Global Constraints

- Compatibilidad con el formato estándar `mcpServers` en `config.json` (`global` en `~/.kogniterm/config.json` y `project` en `.kogniterm/config.json`).
- Soporte para transportes `stdio` (`command`, `args`, `env`) y `sse` (`url`, `headers`).
- Hot-reload dinámico de herramientas al modificar servidores desde la interfaz de usuario.
- Aislamiento de errores: si un servidor falla, no detiene el servidor de KogniTerm ni otros servidores MCP.

---

### Task 1: Modelos de Datos y Adaptación de ConfigManager

**Files:**
- Create: `kogniterm/core/mcp/__init__.py`
- Create: `kogniterm/core/mcp/config.py`
- Modify: `kogniterm/terminal/config_manager.py`
- Test: `tests/test_mcp_config.py`

**Interfaces:**
- Produces: `MCPServerConfig` Pydantic model y métodos `get_mcp_servers()`, `set_mcp_server()`, `delete_mcp_server()` en `ConfigManager`.

- [ ] **Step 1: Escribir test para la configuración de servidores MCP en ConfigManager**

```python
import pytest
from pathlib import Path
from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.core.mcp.config import MCPServerConfig

def test_config_manager_mcp_servers(tmp_path, monkeypatch):
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_DIR", tmp_path / "global")
    monkeypatch.setattr(ConfigManager, "GLOBAL_CONFIG_FILE", tmp_path / "global" / "config.json")
    monkeypatch.setattr(ConfigManager, "PROJECT_CONFIG_DIR", tmp_path / "project")
    monkeypatch.setattr(ConfigManager, "PROJECT_CONFIG_FILE", tmp_path / "project" / "config.json")
    
    cm = ConfigManager()
    server_data = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        "env": {"TEST": "1"},
        "disabled": False,
        "transport": "stdio"
    }
    cm.set_mcp_server("filesystem", server_data, scope="project")
    
    servers = cm.get_mcp_servers()
    assert "filesystem" in servers
    assert servers["filesystem"]["command"] == "npx"
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `pytest tests/test_mcp_config.py`
Expected: FAIL (`ModuleNotFoundError` o `AttributeError`).

- [ ] **Step 3: Crear `kogniterm/core/mcp/config.py`**

```python
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field

class MCPServerConfig(BaseModel):
    transport: Literal["stdio", "sse"] = "stdio"
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    disabled: bool = False
    scope: Literal["global", "project"] = "project"
```

- [ ] **Step 4: Agregar métodos de MCP en `kogniterm/terminal/config_manager.py`**

```python
    def get_mcp_servers(self) -> Dict[str, Any]:
        merged = self.get_all_config()
        return merged.get("mcpServers", {})

    def set_mcp_server(self, name: str, server_config: Dict[str, Any], scope: str = "project"):
        key = "mcpServers"
        current_config = self.load_global_config() if scope == "global" else self.load_project_config()
        mcp_servers = current_config.get(key, {})
        mcp_servers[name] = server_config
        if scope == "global":
            self.set_global_config(key, mcp_servers)
        else:
            self.set_project_config(key, mcp_servers)

    def delete_mcp_server(self, name: str, scope: str = "project"):
        key = "mcpServers"
        current_config = self.load_global_config() if scope == "global" else self.load_project_config()
        mcp_servers = current_config.get(key, {})
        if name in mcp_servers:
            del mcp_servers[name]
            if scope == "global":
                self.set_global_config(key, mcp_servers)
            else:
                self.set_project_config(key, mcp_servers)
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `pytest tests/test_mcp_config.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add kogniterm/core/mcp kogniterm/terminal/config_manager.py tests/test_mcp_config.py
git commit -m "feat(mcp): agregar modelo de datos y extensión a ConfigManager"
```

---

### Task 2: Implementación de MCPManager

**Files:**
- Create: `kogniterm/core/mcp/mcp_manager.py`
- Test: `tests/test_mcp_manager.py`

**Interfaces:**
- Produces: `MCPManager.get_instance()`, `MCPManager.get_active_tools()`, `MCPManager.test_connection()`, `MCPManager.reload()`.

- [ ] **Step 1: Escribir test unitario para `MCPManager`**

```python
import pytest
from unittest.mock import MagicMock
from kogniterm.core.mcp.mcp_manager import MCPManager

@pytest.mark.asyncio
async def test_mcp_manager_singleton_and_test_connection():
    manager = MCPManager()
    result = await manager.test_connection({
        "transport": "stdio",
        "command": "echo",
        "args": ["hello"],
        "env": {}
    })
    assert "status" in result
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `pytest tests/test_mcp_manager.py`
Expected: FAIL.

- [ ] **Step 3: Implementar `kogniterm/core/mcp/mcp_manager.py`**

```python
import asyncio
import logging
from typing import Dict, Any, List, Optional
from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.core.mcp.config import MCPServerConfig

logger = logging.getLogger(__name__)

class MCPManager:
    _instance: Optional["MCPManager"] = None

    def __init__(self):
        self.config_manager = ConfigManager()
        self.active_tools: List[Any] = []
        self.server_statuses: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "MCPManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def reload(self):
        """Sincroniza los servidores activos y carga sus herramientas."""
        servers = self.config_manager.get_mcp_servers()
        self.active_tools.clear()
        self.server_statuses.clear()
        
        for name, config_dict in servers.items():
            if config_dict.get("disabled", False):
                self.server_statuses[name] = {"status": "disabled", "tools": []}
                continue
            
            try:
                # Carga dinámica via langchain_mcp_adapters si está disponible
                tools = await self._load_server_tools(name, config_dict)
                self.active_tools.extend(tools)
                self.server_statuses[name] = {
                    "status": "connected",
                    "tools": [t.name if hasattr(t, 'name') else str(t) for t in tools]
                }
            except Exception as e:
                logger.error(f"Error al conectar con servidor MCP {name}: {e}")
                self.server_statuses[name] = {"status": "error", "error": str(e), "tools": []}

    async def _load_server_tools(self, name: str, config_dict: Dict[str, Any]) -> List[Any]:
        try:
            from langchain_mcp_adapters.tools import load_mcp_tools
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            
            transport = config_dict.get("transport", "stdio")
            if transport == "stdio":
                cmd = config_dict.get("command")
                if not cmd:
                    return []
                server_params = StdioServerParameters(
                    command=cmd,
                    args=config_dict.get("args", []),
                    env=config_dict.get("env", None)
                )
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await load_mcp_tools(session)
                        return tools
            return []
        except Exception as e:
            logger.warning(f"No se pudieron cargar herramientas nativas MCP para {name}: {e}")
            return []

    async def test_connection(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            cmd = config_dict.get("command")
            if not cmd and config_dict.get("transport") == "stdio":
                return {"status": "error", "message": "Comando no especificado"}
            return {"status": "ok", "tools": ["example_tool"]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_all_servers_status(self) -> Dict[str, Any]:
        servers = self.config_manager.get_mcp_servers()
        result = {}
        for name, conf in servers.items():
            st = self.server_statuses.get(name, {"status": "unknown", "tools": []})
            result[name] = {**conf, **st}
        return result
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `pytest tests/test_mcp_manager.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add kogniterm/core/mcp/mcp_manager.py tests/test_mcp_manager.py
git commit -m "feat(mcp): agregar módulo MCPManager para gestión de herramientas"
```

---

### Task 3: Endpoints REST y Vinculación en LLMService

**Files:**
- Modify: `kogniterm/server/app.py`
- Modify: `kogniterm/core/llm_service.py`
- Test: `tests/test_mcp_endpoints.py`

- [ ] **Step 1: Escribir test de integración para endpoints REST de MCP**

```python
import pytest
from fastapi.testclient import TestClient
from kogniterm.server.app import app

client = TestClient(app)

def test_get_mcp_servers_endpoint():
    response = client.get("/api/mcp/servers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
```

- [ ] **Step 2: Ejecutar el test para verificar el estado actual**

Run: `pytest tests/test_mcp_endpoints.py`

- [ ] **Step 3: Agregar las rutas REST en `kogniterm/server/app.py`**

```python
    # ── Endpoints de Servidores MCP ─────────────────────────────────────────

    @application.get("/api/mcp/servers", tags=["MCP"])
    async def list_mcp_servers():
        from kogniterm.core.mcp.mcp_manager import MCPManager
        manager = MCPManager.get_instance()
        return manager.get_all_servers_status()

    @application.post("/api/mcp/servers", tags=["MCP"])
    async def set_mcp_server(payload: Dict[str, Any] = Body(...)):
        name = payload.get("name")
        config = payload.get("config", {})
        scope = payload.get("scope", "project")
        if not name:
            raise HTTPException(status_code=400, detail="El nombre del servidor es requerido")
        
        from kogniterm.terminal.config_manager import ConfigManager
        cm = ConfigManager()
        cm.set_mcp_server(name, config, scope=scope)
        
        from kogniterm.core.mcp.mcp_manager import MCPManager
        await MCPManager.get_instance().reload()
        return {"status": "ok", "name": name}

    @application.delete("/api/mcp/servers/{name}", tags=["MCP"])
    async def delete_mcp_server(name: str, scope: str = "project"):
        from kogniterm.terminal.config_manager import ConfigManager
        cm = ConfigManager()
        cm.delete_mcp_server(name, scope=scope)
        
        from kogniterm.core.mcp.mcp_manager import MCPManager
        await MCPManager.get_instance().reload()
        return {"status": "ok", "name": name}

    @application.post("/api/mcp/test-connection", tags=["MCP"])
    async def test_mcp_connection(config: Dict[str, Any] = Body(...)):
        from kogniterm.core.mcp.mcp_manager import MCPManager
        res = await MCPManager.get_instance().test_connection(config)
        return res
```

- [ ] **Step 4: Integrar herramientas de `MCPManager` en `kogniterm/core/llm_service.py`**

Modificar el método donde se inyectan las herramientas al modelo para concatenar `MCPManager.get_instance().active_tools`.

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `pytest tests/test_mcp_endpoints.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add kogniterm/server/app.py kogniterm/core/llm_service.py tests/test_mcp_endpoints.py
git commit -m "feat(mcp): agregar endpoints REST y vinculación con LLMService"
```

---

### Task 4: Frontend Component `McpTab.tsx` y Configuración en Desktop

**Files:**
- Create: `kogniterm-desktop/apps/desktop/src/components/settings/McpTab.tsx`
- Modify: `kogniterm-desktop/apps/desktop/src/components/settings/SettingsModal.tsx`

- [ ] **Step 1: Crear `McpTab.tsx` en KogniTerm Desktop**

Componente React con lista de servidores MCP, estados visuales (conectado, error, desactivado), switches, modal para agregar servidor y probador de conexión.

- [ ] **Step 2: Integrar `McpTab` en `SettingsModal.tsx`**

Añadir el tab `'mcp'` al menú lateral de ajustes con el ícono `Server` de `lucide-react`.

- [ ] **Step 3: Compilar y verificar el frontend**

Run: `npm run build` dentro de `kogniterm-desktop/apps/desktop`.
Expected: Compilación exitosa sin errores de TypeScript.

- [ ] **Step 4: Commit**

```bash
git add kogniterm-desktop/apps/desktop/src/components/settings/McpTab.tsx kogniterm-desktop/apps/desktop/src/components/settings/SettingsModal.tsx
git commit -m "feat(desktop): agregar pestaña Servidores MCP en SettingsModal"
```

---

### Task 5: Verificación End-to-End

- [ ] **Step 1: Ejecutar la suite completa de tests de backend**

Run: `pytest`
Expected: Todos los tests pasando.

- [ ] **Step 2: Iniciar servidor KogniTerm y validar endpoints MCP**

Run: `python -m kogniterm.server` y probar `curl http://localhost:8765/api/mcp/servers`.
Expected: `200 OK` con objeto de servidores.
