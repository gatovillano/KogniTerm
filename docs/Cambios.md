# 📋 Registro de Cambios - KogniTerm

Este archivo documenta los cambios importantes en cada versión de KogniTerm.

---

## [0.5.0] - 2025-05-22

### 🚀 Nuevas Características

#### Instalación Simplificada
- **Nuevo script `install.sh`**: Instalación con un solo comando desde GitHub
  ```bash
  curl -fsSL https://raw.githubusercontent.com/gatovillano/KogniTerm/main/install.sh | bash
  ```
- Instalación interactiva con confirmaciones
- Detección automática de dependencias del sistema
- Configuración de entorno virtual automática
- Opción de crear symlink global para acceso directo

#### Arquitectura Cliente-Servidor
- **Migración completa** a arquitectura cliente-servidor
- Actualización de puerto WebSocket
- Inicialización en segundo plano del servicio LLM
- Mejoras en la comunicación entre componentes

#### Sistema de Tiempos Configurables
- **KOGNITERM_API_TIMEOUT_S**: Timeout configurable para APIs
- **KOGNITERM_AGENT_POLL_MS**: Intervalo de polling configurable para agentes

#### Streaming y Continuación Automática
- **Streaming de respuestas** habilitado por defecto
- **Continuación automática** cuando las respuestas se truncan
- **KOGNITERM_MAX_CONTINUATIONS**: Número máximo de intentos de continuación configurable

#### Sistema de Aprobaciones
- Sistema de aprobación para ejecución de comandos
- Mejoras en la interactividad del TUI
- Ajustes de altura dinámicos del terminal

#### Tests Ampliados
- Tests para sistema de autoguardado
- Tests para ajustes de altura del TUI
- Tests para CLI de configuración de Telegram

#### Embeddings Mejorados
- **Cache de modelos** en `~/.kogniterm/models` para evitar descargas repetidas
- **Configuración de CPU por defecto** para mayor compatibilidad
- **KOGNITERM_EMBEDDINGS_MODEL**: Override del modelo de embeddings por variable de entorno
- **KOGNITERM_FORCE_CPU**: Forzar uso de CPU en caso de OOM en CUDA
- Fallback automático a CPU en caso de error de memoria CUDA

#### Correcciones
- Corrección de detección TTY para que el banner se renderice correctamente después de `%reset`
- Actualización del banner del README con nuevo diseño

---

## [0.4.3] - Versión Anterior en PyPI

### Características Principales

#### Sistema de Skills Modular
- **SkillManager** completamente reescrito (642 líneas)
- Compatibilidad con estándar Agent Skills / Skills SH
- Carga dinámica JIT (Just-In-Time)
- 27 skills bundled incluyendo:
  - `file_operations`: Gestión completa de archivos
  - `execute_command`: Ejecución de comandos del sistema
  - `code_analysis`: Análisis estático de código con radon
  - `skill_factory`: Creación de skills personalizadas
  - Y 23+ skills adicionales

#### Agentes Especializados
- **BashAgent** (796 líneas): Orquestador principal con streaming
- **CodeAgent** (446 líneas): Ingeniero de software con validación Markdown
- **ResearcherAgent**: Análisis estático y arquitectónico
- **TelegramAgent**: Integración con Telegram

#### Motor LLM Mejorado
- **LLMService** (1648 líneas): Motor de lenguaje unificado
- **MultiProviderManager**: Soporte para múltiples proveedores
- **Text-to-Tool universal**: Conversión de texto plano a ejecución de herramientas
- Rate limiting por proveedor

#### RAG: Indexado de Código
- **CodebaseIndexer**: Indexación semántica de la base de código
- Chunking adaptativo con solapamiento inteligente
- Respeto automático de exclusiones `.gitignore`
- Embeddings vectoriales para búsqueda por similitud

#### Otras Características
- Sistema de estado global **AgentState** (170 líneas)
- Gestión de mensajes con **MessageManager**
- Persistencia de historial con **HistoryManager**
- Detección de Race Conditions
- Sistema de cola de interrupciones con prioridades
- Soporte para múltiples modelos: OpenAI, Anthropic, Gemini, DeepSeek, Ollama, etc.

---

## Convenciones de Commits

Este proyecto sigue las convenciones de [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nueva característica
- `fix:` Corrección de bug
- `docs:` Cambios en documentación
- `style:` Formato, punto y coma faltante, etc. (sin cambio de código)
- `refactor:` Cambio de código que no corrige bug ni agrega característica
- `test:` Agregar tests faltantes o corregir tests existentes
- `chore:` Cambios en el proceso de build o herramientas auxiliares

---

## [0.5.1] - 2026-05-25

### 🎨 Mejoras Visuales

#### Consistencia del Banner
- **`install.sh`**: El arte ASCII del banner del instalador ahora usa el mismo estilo de la TUI (`░█` en lugar de bloques `██`), manteniendo identidad visual consistente entre el instalador y la aplicación.
- **Experiencia de instalación mejorada**: Se rediseñó por completo la interfaz del terminal para mostrar pasos numerados, barra de progreso interactiva, spinners animados que leen en tiempo real el log de `pip` para detallar qué paquete se está descargando o instalando (evitando la terminal muda) y logs detallados guardados en `/tmp/kogniterm_install_[timestamp].log`.
- **Configuración de LLM interactiva**: Se agregó un nuevo paso interactivo que solicita al usuario seleccionar el proveedor de LLM (OpenAI, Groq, Google Gemini, Anthropic, Ollama, etc.), ingresar el modelo de preferencia y su API key, configurando automáticamente el archivo `.env` del proyecto.
- **Compatibilidad UTF-8 / ASCII**: Se agregó detección automática de la locale del sistema. Si la terminal no soporta UTF-8, todos los caracteres especiales del instalador (barra de progreso, iconos, spinner, banner) degradan automáticamente a equivalentes ASCII estándar. También se puede forzar con `--ascii` o `--no-unicode`.

---

## Versiones Anteriores

Para ver versiones anteriores a 0.4.3, consulta el historial de tags en GitHub:
```bash
git tag --sort=-version:refname
```

---

## [0.6.0] - 2026-06-06

### 📦 Release
- Actualización de versión de `0.5.2` a `0.6.0` en `pyproject.toml`
- Publicación del paquete en PyPI: https://pypi.org/project/kogniterm/0.6.0/
- Limpieza de artefactos de build anteriores (`dist/`, `build/`, `kogniterm.egg-info/`)
- Build generado: `kogniterm-0.6.0-py3-none-any.whl` y `kogniterm-0.6.0.tar.gz`

---

## [0.6.1] - 2026-06-06

### 🐛 Correcciones
- **Fix crítico**: El programa no iniciaba al instalar desde PyPI por dependencias faltantes
- Agregado `chromadb` a las dependencias (requerido por `VectorDBManager`)
- Agregado `google-genai` a las dependencias (requerido por `bash_agent.py`)
- Publicado en PyPI: https://pypi.org/project/kogniterm/0.6.1/

---

## [0.6.2] - 2026-06-06

### 🐛 Correcciones
- **Fix**: Agregado `fastembed` a las dependencias (requerido por `EmbeddingsService`)
- **Fix**: Tema `default` se aplica siempre al iniciar, incluso en instalaciones nuevas sin configuración previa
- Eliminado `crewai` de las dependencias declaradas (ya no se usa en el proyecto)
- Publicado en PyPI: https://pypi.org/project/kogniterm/0.6.2/

---

## [0.6.3] - 2026-06-06

### 🐛 Correcciones — Sistema de temas
- **Fix crítico**: El tema no persistía al seleccionarlo porque `tui_app.py` llamaba a `config_manager.set()` (método inexistente en `ConfigManager`). Corregido a `ConfigManager().set_global_config("theme", theme_name)`.
- **Fix**: `command_processor.py` (TUI) ahora también persiste el tema al seleccionarlo con `/theme`, no solo lo aplicaba visualmente.
- El tema `default` ahora se aplica correctamente en instalaciones nuevas sin configuración previa.
- Publicado en PyPI: https://pypi.org/project/kogniterm/0.6.3/

---

## [0.6.4] - 2026-06-06

### 🐛 Correcciones — Sistema de temas (fix definitivo)
- **Causa raíz encontrada**: El config local del proyecto (`.kogniterm/config.json`) sobreescribía silenciosamente el config global (`~/.kogniterm/config.json`), por lo que el tema nunca persistía al reiniciar desde un proyecto específico.
- **Fix**: Al guardar el tema (desde `/theme` en la TUI), ahora se actualiza **tanto el config global como el local del proyecto** (si existe), asegurando consistencia.
- **Fix**: `apply_theme` ahora acepta `persist=False` para que el `on_mount` no sobreescriba la preferencia guardada al iniciar.
- Publicado en PyPI: https://pypi.org/project/kogniterm/0.6.4/

---

## [0.6.5] - 2026-06-07

### 📦 Correcciones de Empaquetado (Packaging)

- **Fix crítico (ejecución de tool calls)**: Se corrigió un bug en la distribución de PyPI que impedía la ejecución de tool calls cuando la aplicación era instalada vía `pipx` o `pip` desde el repositorio central.
  - **Causa**: Los archivos descriptores de las habilidades (`SKILL.md`) no se incluían en el paquete final distribuido en PyPI. Al faltar los archivos `SKILL.md`, `SkillManager` fallaba en cargar las herramientas, por lo que el LLM recibía una lista vacía de herramientas y las peticiones de tool calls fallaban, apareciendo en su lugar como texto plano en el chat.
  - **Solución**: Se restauró el archivo `MANIFEST.in` y se configuró `include-package-data = true` bajo `[tool.setuptools]` en `pyproject.toml`, forzando a setuptools a incluir de forma recursiva todos los recursos, archivos JSON y archivos descriptores Markdown (`SKILL.md`) de las skills en el build final.
- **Nuevo Script de Instalación**: Se creó un script `install.sh` desde cero para facilitar la instalación en un entorno virtual aislado (`venv`), crear los accesos directos o alias globales (`kogniterm` y `kogniterm-server` en `~/.local/bin`) y guiar al usuario a través del asistente interactivo de configuración (proveedor, modelo, API keys persistidos en el JSON de usuario y el setup del bot de Telegram para el servidor). Además, se añadió la redirección de entrada estándar (`exec < /dev/tty`) haciendo que el script sea compatible con comandos de instalación directa desde la web (ej: `bash -c "$(curl ...)"`).
- **Restauración de kogniterm-server**: Se reincorporó el comando `kogniterm-server = "kogniterm.server.__main__:main"` al listado de scripts en `pyproject.toml` para que sea compilado durante la instalación de pip y se expuso globalmente con su respectivo script lanzador (wrapper), habilitando la funcionalidad del servidor y el Bot de Telegram de forma global.
- **Actualización de Documentación**: Se actualizó el archivo `README.md` estableciendo el script de instalación `bash -c "$(curl ...)"` como el método de instalación oficial y recomendado para los usuarios, manteniendo las opciones tradicionales de PyPI como alternativas.

---

## [0.6.6] - 2026-06-07

### 🐛 Correcciones — Descubrimiento de Skills y Conflictos de Rutas

- **Fix crítico (carga de skills en instalación global)**: Se corrigió un bug por el cual no se cargaban las skills (cargándose 0 herramientas) cuando KogniTerm era instalado en una ruta global que contuviera carpetas ocultas o de soporte (como `~/.kogniterm/repo`).
  - **Causa**: `SkillManager` filtraba directorios ocultos haciendo `any(part.startswith('.') or part.startswith('_') for part in skill_dir.parts)`. Al usar `parts` sobre la ruta absoluta, si el directorio base de la aplicación comenzaba con un punto (ej. `.kogniterm`), todas las skills se descartaban silenciosamente.
  - **Solución**: Se modificó la validación para verificar el nombre de los directorios relativos al directorio de búsqueda (`base_dir` o `clone_dir` en el adaptador de skills), garantizando que las carpetas superiores no afecten al filtro.
- **Limpieza de procesos y conflictos**: Se identificaron y eliminaron procesos obsoletos colgados en segundo plano procedentes de instalaciones anteriores que mantenían en memoria la versión antigua del software.

---

## [0.6.7] - 2026-06-07

### 🐛 Correcciones — Adaptador de Telegram y Gestión de Respuestas

- **Fix crítico (envío de respuestas al bot de Telegram)**: Se corrigió un bug por el cual las respuestas producidas por el agente no llegaban al bot de Telegram cuando el usuario interactuaba.
  - **Causa**: En `ChannelAdapter.send_message`, la tarea de procesamiento de eventos en segundo plano (`process_task`) se cancelaba de manera agresiva tras esperar solo 200 ms (`asyncio.sleep(0.2)`) desde que finalizaba la invocación del agente. Debido a que las llamadas de red a la API de Telegram tardan comúnmente más de 200 ms, la tarea se cancelaba a mitad de camino (`asyncio.CancelledError`), interrumpiendo el envío de la respuesta.
  - **Solución**: Se sustituyó el sleep fijo y la cancelación inmediata por una espera asíncrona segura de hasta 10 segundos utilizando `asyncio.wait_for(process_task, timeout=10.0)`, garantizando que la tarea finalice de forma natural tras vaciar la cola de eventos y enviar la respuesta.
- **Formateo de respuestas y payloads**:
  - Se corrigió la extracción de texto en eventos de tipo `"message"` y `"error"`. Dado que `ServerUI` emite estos eventos estructurados en diccionarios (ej. `{"text": ...}` y `{"message": ...}`), al pasarse directamente al limpiador se serializaban como strings crudos de Python (ej. `"{'text': '...'}"`). Ahora se extrae el texto de forma segura si el payload es un diccionario.
- **Soporte de nuevos eventos**:
  - Se actualizaron los adaptadores `TelegramAdapter`, `SlackAdapter` y `CLIAdapter` para que soporten de forma nativa y retrocompatible los nuevos eventos `"tool_call"` (que reemplaza a `"tool_start"`) y `"tool_result"` (que reemplaza a `"tool_output"`), asegurando que el estado del agente y el inicio/fin de herramientas se reporten de forma consistente.
- **Mejoras de depuración y logs**:
  - Se modificó `_process_events` para registrar la traza de excepción completa (`logger.exception`) si ocurre un error enviando eventos al canal.
  - Se añadieron alertas informativas y preventivas en `TelegramAdapter.send_to_channel` cuando no hay un `chat_id` o no está inicializada la instancia de la aplicación, evitando retornos silenciosos.
  - Se agregaron validaciones de contenido en el envío de mensajes a Telegram para evitar peticiones fallidas debido a strings de texto vacíos.
  - Se añadieron logs informativos detallados en el evento `done` de `TelegramAdapter` para indicar si el texto acumulado del stream está vacío, su longitud y si se envía correctamente.

---

## [0.6.8] - 2026-06-07

### 🐛 Correcciones — Streaming Nativo y Concurrencia en Telegram

- **Fix crítico (Respuestas vacías en Telegram / REST)**: Se solucionó el problema por el cual los mensajes procesados en el servidor no enviaban respuesta a Telegram (el texto acumulado quedaba vacío).
  - **Causa**: El agente (`call_model_node` en [bash_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/bash_agent.py#L450)) canalizaba toda la respuesta generada por el LLM a través de `terminal_ui.update_live` para actualizar el display interactivo. Sin embargo, no emitía eventos `"stream"` individuales. Como `TelegramAdapter` y otros servicios síncronos consumen únicamente la cola de `"stream"`, el texto acumulado al final resultaba vacío.
  - **Solución**: Se modificó `call_model_node` para que si el `terminal_ui` es la interfaz del servidor (`ServerUI`), se emita de manera activa cada fragmento de la respuesta llamando a `terminal_ui.print_stream(part)`.
- **Implementación de Streaming Nativo en Telegram**:
  - Se habilitó la nueva función `sendMessageDraft` de la API de bots de Telegram (versión 9.3+).
  - Ahora el adaptador de Telegram envía de forma incremental los fragmentos de la respuesta del LLM a la interfaz de chat en tiempo real a través del método de borrador efímero (`_send_message_draft`), confirmando la respuesta con `sendMessage` normal solo cuando llega el evento `"done"`.
- **Corrección de Concurrencia y Seguridad Multiusuario**:
  - Se eliminó el uso de variables globales mutables de instancia en `TelegramAdapter` (`self._current_chat_id`, `self._stream_text`, `self._draft_id`).
  - Se modificó la firma de `send_to_channel` en todos los adaptadores (`ChannelAdapter`, `CLIAdapter`, `WebhookAdapter`, `SlackAdapter`, `TelegramAdapter`) para aceptar un `session_id` opcional.
  - Se estructuró el acumulador de streams (`_stream_texts`) y los IDs de borrador (`_draft_ids`) como diccionarios indexados por el `chat_id` extraído del `session_id`, garantizando que múltiples usuarios chateando concurrentemente con el bot tengan flujos aislados y no mezclen sus respuestas.

---

## [0.6.9] - 2026-06-08

### 🐛 Correcciones — Configuración de Gemini (Google AI Studio)

- **Fix crítico (Vertex_ai_betaException al seleccionar Google AI Studio)**: Se solucionó el error inesperado `litellm.NotFoundError: Vertex_ai_betaException - b'404 page not found'` que ocurría al seleccionar Google AI Studio como proveedor.
  - **Causa**: LiteLLM requiere que se configure la variable de entorno `GEMINI_API_KEY` para dirigir las llamadas con prefijo `gemini/` a Google AI Studio. Si esta variable no está presente, LiteLLM intenta de manera predeterminada enrutar la llamada a Google Vertex AI. Como la aplicación solo definía `LITELLM_API_KEY` y le pasaba la clave directamente en la invocación sin especificar la API de origen, LiteLLM intentaba instanciar y usar el cliente de Vertex AI, fallando con un error 404 al no tener credenciales ni recursos de GCP configurados.
  - **Solución**:
    1. Se modificó [provider_config.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm/provider_config.py) para que exporte explícitamente `GEMINI_API_KEY` en `os.environ` cuando el proveedor detectado es Gemini, e inyecte `custom_llm_provider = "gemini"` en los parámetros de completion para forzar la API nativa de Google AI Studio.
    2. Se actualizó [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py) en su constructor y en el método `set_model` para exportar de manera consistente `os.environ["GEMINI_API_KEY"]` al inicializar o cambiar el modelo a Gemini, y se añadió el parámetro `custom_llm_provider = "gemini"` en la preparación de parámetros de completion.
    3. Se modificó [multi_provider_manager.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/multi_provider_manager.py) para inyectar `custom_llm_provider = "gemini"` en las llamadas realizadas por el gestor de múltiples proveedores si el modelo es Gemini (evitando el fallback incorrecto a Vertex AI).

---

## [0.6.10] - 2026-06-08

### 💬 Interacción con el Usuario

- **Saludo**: Se respondió al saludo del usuario con el mensaje "Hola Mundo" según lo solicitado.

---

## [0.6.11] - 2026-06-08

### 🚀 Nuevas Características — Integración de Google Antigravity Session Auth
- **Cliente Antigravity (`AntigravityClient`)**:
  - Implementación completa de `run_login_flow()` para autenticación interactiva mediante OAuth2 (Consent Screen de Google) usando un servidor HTTP local callback en el puerto `36742`.
  - Persistencia segura del token de sesión en `~/.gemini/antigravity-cli/antigravity-oauth-token`, compatible con la CLI `agy`.
  - Renovación y obtención automática del token de acceso (refresh token flow) con endpoints de Google OAuth2.
  - Resolución dinámica de `Project ID` a través de `v1internal:loadCodeAssist`.
  - Método dinámico `fetch_available_models()` que consulta `v1internal:fetchAvailableModels` para obtener la lista real de modelos disponibles del proyecto en Google Cloud, procesando la estructura de diccionario de modelos devuelta por la API, con fallback integrado a modelos por defecto.
  - Corregida decodificación de `client_secret` en base64 corrigiendo un carácter faltante en la clave de Google OAuth.
  - Soporte de invocación para modelos `antigravity/` (con streaming compatible SSE y retorno estructurado de tool calls).
- **Integración TUI y Meta-Comandos**:
  - Registro del nuevo meta-comando `/agy-login` en la terminal para iniciar, renovar o cerrar la sesión de Antigravity.
  - Inclusión del proveedor `Antigravity` en la selección de proveedores de la TUI (`/provider`), con aviso interactivo y redirección al inicio de sesión si no existe una sesión activa.
  - Soporte para listar dinámicamente los modelos de Antigravity mediante llamada a la API real bajo el comando `/models` cuando el proveedor activo es `antigravity`.
  - Integración completa de `/agy-login` y `%agy-login` en el sistema de autocompletado y sugerencias del prompt en la terminal (`tui_app.py` y `file_completer.py`).
- **Enrutamiento en `MultiProviderManager` y `LLMService`**:
  - Enrutamiento dinámico y directo al cliente `AntigravityClient` en `MultiProviderManager.execute()` cuando se selecciona el proveedor `antigravity`, evitando la dependencia de LiteLLM para tokens dinámicos.
  - Inicialización sin API Key local requerida en `LLMService` cuando el modelo tiene el prefijo `antigravity/`.
- **Pruebas de Integración y Regresión**:
  - Creación de un suite de pruebas completo en `tests/test_antigravity_integration.py` que valida el inicio de sesión, el refresco de tokens, la obtención del Project ID, la respuesta/streaming del modelo, y la obtención exitosa/fallback de los modelos disponibles.

---

## [0.6.12] - 2026-06-08

### 🐛 Corrección — Tool calls multi-turno en Antigravity (400 Bad Request)
- **Causa raíz real**: El campo `thought_signature` que incluye el API en cada `functionCall` part debe preservarse a lo largo de toda la cadena de serialización para que esté disponible en el segundo turno. El problema no era solo en `antigravity_client.py` sino en `llm_service.py`, que descartaba el campo durante la acumulación del streaming y al crear el `AIMessage`.
- **Solución (cadena completa)**:
  1. `AntigravityClient` (streaming): extrae `thoughtSignature` de cada part y lo adjunta al `SimpleNamespace` del tool call.
  2. `llm_service.py` (acumulación): captura `thought_signature` del `SimpleNamespace` y lo guarda en el dict de acumulación.
  3. `llm_service.py` (final_tool_calls): propaga `thought_signature` al dict de `final_tool_calls`.
  4. `llm_service.py` (_message_to_litellm_format): incluye `thought_signature` en el dict serializado del tool call del `AIMessage`.
  5. `AntigravityClient.map_messages()`: re-inyecta `thoughtSignature` en el `functionCall` part al reconstruir el historial del turno siguiente.
- **Sin impacto en otros proveedores**: el campo solo aparece cuando fue generado por Antigravity; todos los checks son condicionales.


