# Diseño Técnico: Integración de Servidores MCP en KogniTerm y KogniTerm Desktop

**Fecha:** 2026-08-20  
**Estado:** Aprobado  
**Objetivo:** Permitir la configuración y ejecución dinámica de servidores MCP (Model Context Protocol) tanto por `stdio` como por `sse` desde KogniTerm Desktop y el motor backend KogniTerm.

---

## 1. Visión General

La integración de servidores MCP (Model Context Protocol) extiende las capacidades de los agentes de KogniTerm (`CodeAgent`, `BashAgent`, `ResearcherAgent`) permitiendo la conexión a fuentes de datos y herramientas externas estándar (archivos, bases de datos, APIs de terceros, etc.).

La configuración sigue el esquema estándar `mcpServers` (compatible con Claude Desktop y Cursor) almacenado en `~/.kogniterm/config.json` (Global) y `.kogniterm/config.json` (Proyecto).

---

## 2. Arquitectura de Componentes

### 2.1 Backend (`kogniterm`)

1. **`kogniterm/core/mcp/config.py`**:
   - Modelos Pydantic para `MCPServerConfig` (`command`, `args`, `env`, `url`, `headers`, `transport`, `disabled`, `scope`).
2. **`kogniterm/core/mcp/mcp_manager.py`**:
   - `MCPManager`: Gestor singleton de conexiones a servidores MCP (`stdio` y `sse`).
   - Usa `langchain_mcp_adapters` o cliente MCP nativo para descubrir herramientas y convertirlas a `LangChain BaseTool`.
   - Soporta prueba de conexión en caliente y aislamiento de fallos.
3. **`kogniterm/server/app.py`**:
   - Endpoints REST `/api/mcp/servers`, `/api/mcp/servers/{name}`, `/api/mcp/servers/{name}/toggle`, `/api/mcp/test-connection`.
4. **`kogniterm/core/llm_service.py`**:
   - Inyección automática de herramientas MCP en el bind de herramientas del LLM.

### 2.2 Frontend (`kogniterm-desktop`)

1. **`kogniterm-desktop/apps/desktop/src/components/settings/McpTab.tsx`**:
   - UI para ver servidores MCP, estado de conexión, agregar, editar, eliminar, probar conexión y conmutar estado On/Off.
2. **`kogniterm-desktop/apps/desktop/src/components/settings/SettingsModal.tsx`**:
   - Integración de la pestaña "Servidores MCP" (`mcp`).
3. **TypeScript Types (`src/types/mcp.ts` / `packages/types`)**:
   - Interfaces para servidores MCP y resultados de test.

---

## 3. Esquema de Configuración

Almacenado en `config.json`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
      "env": {},
      "disabled": false
    },
    "custom-sse": {
      "transport": "sse",
      "url": "http://localhost:8000/sse",
      "headers": {},
      "disabled": false
    }
  }
}
```

---

## 4. Plan de Verificación

1. **Pruebas de Backend**:
   - Verificación de carga de configuración global y por proyecto.
   - Conexión simulada o real a un servidor MCP por `stdio` (ej. `npx @modelcontextprotocol/server-filesystem`).
   - Prueba del endpoint `/api/mcp/test-connection`.
2. **Pruebas de Frontend**:
   - Verificación del formulario de creación y edición en `SettingsModal`.
   - Verificación del interruptor de activación y actualización de lista de herramientas.
