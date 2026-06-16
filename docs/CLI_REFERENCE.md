# KogniTerm — Referencia de Comandos CLI

Esta referencia cubre todos los comandos disponibles desde la terminal (fuera de la TUI).

---

## `kogniterm` — Terminal de IA

Lanza la interfaz TUI principal. Sin argumentos, abre el modo interactivo.

```bash
kogniterm             # Inicia la TUI (modo interactivo)
kogniterm -y          # Modo auto-aprobación (ejecuta comandos sin pedir confirmación)
kogniterm --yes       # Alias de -y
```

> **Modo híbrido:** Si `kogniterm-server` está corriendo en `localhost:8765`, la TUI se conecta automáticamente y delega toda la lógica al backend. Si no está disponible, opera en modo local sin cambios.

---

## `kogniterm-server` — Backend persistente

Lanza el servidor FastAPI con soporte WebSocket, SSE y REST. **El agente sobrevive a cierres de la TUI.**

```bash
kogniterm-server                          # Escucha en 0.0.0.0:8765 (default)
kogniterm-server --host 127.0.0.1         # Restringir a localhost
kogniterm-server --port 9000              # Cambiar puerto
kogniterm-server --reload                 # Hot-reload (modo desarrollo)
```

**Endpoints disponibles al iniciar:**
| URL | Descripción |
|-----|-------------|
| `http://localhost:8765/docs` | Documentación Swagger interactiva |
| `http://localhost:8765/health` | Health check y sesiones activas |
| `ws://localhost:8765/ws/<session_id>` | Canal WebSocket principal |
| `http://localhost:8765/sse/<session_id>?message=...` | Server-Sent Events |

---

## `kogniterm config` — Configuración global

Gestiona la configuración persistente en `~/.kogniterm/config.json`.

### Configuración general

```bash
# Establecer un valor de configuración global
kogniterm config set <clave> <valor>

# Establecer un valor solo para el proyecto actual
kogniterm config project set <clave> <valor>

# Leer un valor de configuración
kogniterm config get <clave>

# Listar toda la configuración
kogniterm config list
```

**Ejemplos:**
```bash
kogniterm config set default_model gemini/gemini-2.0-flash-exp
kogniterm config set theme dark
kogniterm config set reasoning_effort high
kogniterm config project set default_model openrouter/google/gemini-2.0-flash-exp:free
```

---

### `kogniterm config telegram` — Bot de Telegram

Asistente interactivo para configurar el bot de Telegram del servidor.

```bash
kogniterm config telegram               # Asistente guiado paso a paso
kogniterm config telegram setup         # Alias del comando anterior
kogniterm config telegram status        # Ver configuración actual del bot
kogniterm config telegram show          # Alias de status
kogniterm config telegram enable        # Activar el bot
kogniterm config telegram disable       # Desactivar el bot (sin borrar)
```

**Flujo del asistente (`setup`):**
1. Solicita el nombre del bot (ej: `mi_bot`)
2. Solicita el token de BotFather
3. Pregunta si activarlo de inmediato
4. Detecta automáticamente el `chat_id` privado esperando un mensaje tuyo al bot
5. Guarda todo en `.kogniterm/server_config.json`

> Tras configurarlo, reinicia el servidor con `kogniterm-server` para que el bot se active.

---

## `kogniterm keys` — API Keys

Gestiona las API keys de los proveedores de LLM.

```bash
# Guardar una API key para un proveedor
kogniterm keys set <proveedor> <api_key>

# Listar el estado de todas las keys (enmascaradas)
kogniterm keys list

# Configurar Ollama local
kogniterm keys set ollama_mode local
kogniterm keys set ollama_mode cloud

# Cambiar la URL base de Ollama
kogniterm keys set ollama_api_base http://localhost:11434
```

**Proveedores soportados:**
| Proveedor | Comando |
|-----------|---------|
| Google AI Studio | `kogniterm keys set google AIza...` |
| OpenAI | `kogniterm keys set openai sk-...` |
| Anthropic | `kogniterm keys set anthropic sk-ant-...` |
| OpenRouter | `kogniterm keys set openrouter sk-or-...` |
| Ollama (cloud) | `kogniterm keys set ollama_cloud ...` |
| LiteLLM proxy | `kogniterm keys set litellm ...` |

---

## `kogniterm models` — Configuración del modelo LLM

```bash
# Cambiar el modelo activo (persiste para todas las interfaces)
kogniterm models use <nombre_del_modelo>

# Ver el modelo configurado actualmente
kogniterm models current
```

**Ejemplos:**
```bash
kogniterm models use gemini/gemini-2.0-flash-exp
kogniterm models use openrouter/google/gemini-2.0-flash-exp:free
kogniterm models use anthropic/claude-3-5-sonnet-20240620
kogniterm models use ollama/llama3
kogniterm models use antigravity/gemini-3.1-pro-high
```

---

## `kogniterm init` — Inicializar contexto del proyecto

Analiza el repositorio actual y genera la memoria contextual del proyecto (`.kogniterm/llm_context.md`) + indexa el código para búsquedas semánticas (RAG).

```bash
kogniterm init               # Inicializar (salta si ya existe llm_context.md)
kogniterm init --force       # Forzar regeneración aunque ya exista
kogniterm init -f            # Alias de --force
```

**Qué hace:**
1. Escanea la estructura del proyecto (README, pyproject.toml, package.json, etc.)
2. Genera `.kogniterm/llm_context.md` — memoria contextual para el agente
3. Indexa el código fuente en la base de datos vectorial (ChromaDB) para búsquedas semánticas

---

## `kogniterm index` — Indexación del código (RAG)

Gestiona manualmente la base de datos vectorial de código.

```bash
# Re-indexar el proyecto actual
kogniterm index refresh

# Limpiar la base de datos vectorial
kogniterm index clean-db
kogniterm index --clear       # Alias
```

---

## `kogniterm skills` — Gestión de skills externas

Instala y gestiona skills adicionales para el agente.

```bash
# Instalar una skill desde un repositorio GitHub
kogniterm skills add <repo_url>
kogniterm skills add <repo_url> --skill <nombre>

# Buscar skills en el catálogo de skills.sh
kogniterm skills search <query>

# Listar skills externas instaladas
kogniterm skills list

# Eliminar una skill instalada
kogniterm skills remove <nombre>

# Ver información detallada de una skill
kogniterm skills info <nombre>
```

**Ejemplos:**
```bash
kogniterm skills add https://github.com/user/mi-skill-repo
kogniterm skills search react
kogniterm skills list
kogniterm skills info file_operations
kogniterm skills remove mi_skill_vieja
```

---

## Variables de entorno

Puedes sobreescribir la configuración via variables de entorno antes de lanzar KogniTerm:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `KOGNITERM_SERVER_URL` | URL WebSocket del servidor | `ws://127.0.0.1:8765` |
| `KOGNITERM_SESSION_ID` | ID de sesión del agente | `tui-default` |
| `LITELLM_MODEL` | Modelo LLM a usar | (guardado en config) |
| `GOOGLE_API_KEY` | API key de Google AI | (guardado en config) |
| `OPENAI_API_KEY` | API key de OpenAI | (guardado en config) |
| `ANTHROPIC_API_KEY` | API key de Anthropic | (guardado en config) |
| `OPENROUTER_API_KEY` | API key de OpenRouter | (guardado en config) |
| `OLLAMA_API_BASE` | URL base de Ollama local | `http://127.0.0.1:11434` |
| `KOGNITERM_REASONING_EFFORT` | Esfuerzo de razonamiento | `medium` |
| `KOGNITERM_API_TIMEOUT_S` | Timeout de la API (segundos) | `60` |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram | (config telegram) |

**Ejemplo de uso:**
```bash
LITELLM_MODEL=gemini/gemini-2.0-flash-exp GOOGLE_API_KEY=AIza... kogniterm
```

---

## Comandos dentro de la TUI

Una vez dentro de la interfaz interactiva, usa estos comandos con `/` o `%`:

| Comando | Descripción |
|---------|-------------|
| `/help` | Mostrar ayuda general |
| `/models` | Listar modelos disponibles |
| `/provider` | Cambiar proveedor de LLM |
| `/keys` | Gestionar API keys |
| `/theme` | Cambiar tema visual (`dark`, `light`, `nord`, etc.) |
| `/reset` | Limpiar el historial de conversación |
| `/undo` | Deshacer el último turno |
| `/session` | Gestionar sesiones guardadas |
| `/resume <nombre>` | Cargar una sesión guardada |
| `/init` | Inicializar memoria del proyecto |
| `/skills` | Ver skills disponibles |
| `/instructions` | Añadir instrucciones personalizadas al sistema |
| `/reasoning` | Cambiar el nivel de razonamiento |
| `/summarymodel` | Cambiar el modelo usado para resumir el historial |
| `/compress` | Comprimir/resumir el historial actual |
| `/agy-login` | Autenticar con Google Antigravity |
| `esc` | Interrumpir la generación en curso |
| `ctrl+o` | Mostrar/Ocultar panel de salida de herramientas |
| `ctrl+b` | Mostrar/Ocultar panel de seguimiento de tareas |
