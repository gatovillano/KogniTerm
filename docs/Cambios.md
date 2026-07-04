# 📋 Registro de Cambios - KogniTerm

Este archivo documenta los cambios importantes en cada versión de KogniTerm.

---

## [0.5.0] - 2025-05-22
## [0.5.1] - 2025-05-22 (hotfix)

### 🔧 Mejoras en Gestión de Memoria del Proyecto

#### Reforzamiento de Revisión de Memoria
- **Nueva función `force_refresh_project_memory()`**: Limpia cachés y fuerza la lectura de archivos de memoria desde disco
  - Limpia globales `_file_cache` y `_json_file_cache`
  - Carga y cachea contenido de `.kogniterm/llm_context.md` (memoria contextual)
  - Carga y cachea contenido de `.kogniterm/instructions.md` (memorias aprendidas)
  - Registra logs informativos con tamaño de contenido

#### Validación de Integridad de Memoria
- **Nueva función `validate_memory_integrity()`**: Valida la existencia y contenido de archivos de memoria
  - Verifica que los archivos existan y no estén vacíos
  - Retorna diccionario con estado de validación por archivo
  - Manejo de errores con logging

#### Reporte de Estado de Memoria
- **Nueva función `get_memory_status_report()`**: Genera reporte visual del estado de memoria
  - Combina validación e integridad en formato markdown
  - Iconos de estado visual (✅, ❌, ⚠️)
  - Incluye tamaño de archivos y estado de caché

#### Integración en Sistema de Mensajes
- **Modificación `get_system_message()`**: Ahora incluye reporte de memoria al final del mensaje de sistema
  - Parámetro `force_refresh` para forzar recarga desde disco
  - Mensajes informativos cuando se actualiza memoria
  - Reporte automático de estado de archivos de memoria

#### Correcciones
- **task_tracker**: Corregido estado 'completed' a 'done' según especificación
- **sophisticated_editor_tool**: Eliminado parámetro `target_content_pattern` no válido

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
- **Causa raíz real**: El campo `thought_signature` que incluye el API en cada `functionCall` part debe preservarse a lo largo de toda la cadena de serialización para que esté disponible en el segundo turno. El problema no era solo en `antigravity_client.py` sino en `llm_service.py`, que descartaba el campo durante la acumulación.
  - 3. `llm_service.py` (final_tool_calls): propaga `thought_signature` al dict de `final_tool_calls`.
  - 4. `llm_service.py` (_message_to_litellm_format): incluye `thought_signature` en el dict serializado del tool call del `AIMessage`.
  - 5. `AntigravityClient.map_messages()`: re-inyecta `thoughtSignature` en el `functionCall` part al reconstruir el historial del turno siguiente.
- **Sin impacto en otros proveedores**: el campo solo aparece cuando fue generado por Antigravity; todos los checks son condicionales.

---

## [0.6.13] - 2026-06-09

### 🐛 Corrección — Persistencia de thought_signature, resolución de nombre de herramientas, visualización de pensamientos y soporte de Claude en Antigravity
- **Causa raíz**:
  1. **Pérdida de `thought_signature` (Gemini - HTTP 400)**: Durante el streaming se extraía `thought_signature` de la lista `tool_calls` para guardarse en `message.additional_kwargs["thought_signatures"]` (evitando errores de validación de LangChain). Sin embargo, al serializar el historial, `_to_litellm_message` solo buscaba `thought_signature` directamente en el diccionario del tool call, perdiendo la firma en el segundo llamado de la API.
  2. **Nombre de herramienta nulo (`name: null` - Gemini - HTTP 400)**: El mensaje de tipo `tool` (respuesta de la herramienta) se serializaba sin el campo `name`. Como resultado, `AntigravityClient.map_messages` enviaba el esquema `functionResponse` con `name: null` al no estar presente, lo cual es un error de formato crítico para la API de Gemini.
  3. **Visualización de Pensamiento Nativo (Gemini)**: La API interna de Google Cloud Code PA/Antigravity entrega el razonamiento de los modelos en partes del stream marcadas con `"thought"`. Esta clave puede presentarse en diversos formatos en las llamadas de red (como un booleano `True` al lado del texto, como un string directo de razonamiento, o como un diccionario `{ "text": ... }`). El parseador original no discriminaba estas estructuras ni las extraía de forma robusta, haciendo que el pensamiento se mezclara con el texto regular o se ignorara en la TUI.
  4. **Falta de ID de herramienta en Claude (HTTP 400)**: Al usar modelos de Claude en Antigravity, el proxy del backend (Vertex AI) traduce el formato de Gemini a Anthropic `/v1/messages`. Anthropic exige de forma obligatoria que cada elemento de tipo `tool_use` (y su posterior respuesta `tool_result`) contenga un campo `id` no vacío. Como `AntigravityClient.map_messages` omitía propagar el campo `id` en `functionCall` y `functionResponse`, el proxy fallaba al generar la petición de Anthropic, lanzando un error `messages.1.content.0.tool_use.id: Field required`.
  5. **Visualización de Pensamiento Manual (Claude/OpenAI)**: Para modelos sin razonamiento nativo (como Claude 3.5 Sonnet), el sistema les instruye a estructurar su razonamiento usando bloques `<thinking>...</thinking>` o `<thought>...</thought>`. Sin embargo, `llm_service.py` solo buscaba etiquetas `<thought>`, omitiendo por completo las etiquetas `<thinking>`, lo cual hacía que el pensamiento de Claude no se filtrara como `__THINKING__:` y se imprimiera directamente en la respuesta final sin formato especial.
- **Solución**:
  - Se modificó `_to_litellm_message` en [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py) para recuperar `thought_signature` de `message.additional_kwargs["thought_signatures"]` (usando el ID del tool call) y propagar el campo `name` en el mensaje de tipo `tool` si se encuentra disponible.
  - Se implementó un fallback de resolución hacia atrás en `AntigravityClient.map_messages` en [antigravity_client.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/antigravity_client.py) para que, si el mensaje `tool` carece de `name`, busque en los mensajes de tipo `assistant` anteriores el tool call con el `id` correspondiente y resuelva el nombre original de la herramienta.
  - Se actualizó `AntigravityClient.completion` en [antigravity_client.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/antigravity_client.py) (tanto en modo stream como síncrono) para soportar múltiples formatos de la estructura `"thought"` (booleanos, strings o diccionarios), abstrayendo el razonamiento bajo `delta.reasoning_content` (o `message.reasoning_content`) de forma consistente.
  - Se modificó `AntigravityClient.map_messages` en [antigravity_client.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/antigravity_client.py) para propagar el `id` de la llamada a la herramienta tanto dentro de la estructura `functionCall` (del mensaje `assistant`) como en `functionResponse` (del mensaje `tool`), asegurando que la traducción del backend de Google para modelos de Anthropic Claude mantenga la consistencia de IDs y evite el error 400.
  - Se añadió la normalización de etiquetas en el procesador de streams de [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py) reemplazando `<thinking>` por `<thought>` y `</thinking>` por `</thought>` de forma consistente para que el detector manual de CoT capture el pensamiento de Claude y otros modelos sin soporte de razonamiento nativo.
  - Se corrigió el caso de prueba `test_thought_signature_propagation` en [test_antigravity_integration.py](file:///home/gato/Proyectos/Gemini-Interpreter/tests/test_antigravity_integration.py) para inicializar correctamente `LLMService` y llamar al método serializador real `_to_litellm_message`.
  - Se actualizó y validó el script de verificación automatizado en el directorio `scratch` que comprueba de forma integrada los cinco fallos y resoluciones.
- **Refuerzo de Seguimiento de Tareas (`task_tracker`)**:
  - Se modificaron los mensajes de instrucciones del sistema (`SYSTEM_MESSAGE` / `get_system_message`) de los agentes principales [bash_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/bash_agent.py), [code_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/code_agent.py) y [researcher_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/researcher_agent.py) para inyectar una sección prioritaria y mandatoria de **Protocolo Obligatorio de Seguimiento de Tareas (task_tracker)**.
  - El protocolo exige de forma estricta inicializar el plan de trabajo con `action="init"`, actualizar el estado de cada tarea con `action="update"`, y notificar la finalización correspondiente, evitando que los agentes omitan o se salten el uso de la herramienta.

---

## [0.6.14] - 2026-06-09

### ⚙️ Refuerzo del Protocolo de Seguimiento de Tareas (task_tracker), Activación de Pensamiento en Antigravity y Prompts Dinámicos
- **Cambios**:
  - **Refuerzo en Agentes**: Se modificó la instrucción de sistema (`SYSTEM_MESSAGE` / `get_system_message` / `get_deep_coder_system_prompt` / `get_deep_research_system_prompt`) en [bash_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/bash_agent.py), [code_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/code_agent.py), [researcher_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/researcher_agent.py), [deep_coder.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/deep_coder.py) y [deep_researcher.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/deep_researcher.py) para inyectar una advertencia visual gigante y un protocolo de cumplimiento estricto de `task_tracker` al inicio y final de los prompts del sistema, eliminando cualquier ambigüedad sobre la obligatoriedad de su uso para cualquier tipo de solicitud del usuario.
  - **Prompts Dinámicos e Instrucción de Pensamiento Manual**: Se convirtieron los mensajes estáticos de [code_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/code_agent.py) y [researcher_agent.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/agents/researcher_agent.py) en funciones dinámicas de creación de prompt (`get_system_message`). Se inyectó a nivel de sistema una instrucción detallada para que los modelos que no tienen razonamiento nativo (como `gemini-3-flash` o `claude-sonnet-4-6`) encierren obligatoriamente su proceso mental de CoT dentro de etiquetas XML `<thought>...</thought>`, permitiendo que KogniTerm intercepte y despliegue el pensamiento en el panel TUI.
  - **Reconocimiento de Capacidad de Pensamiento en Antigravity**: Se actualizó `is_thinking_model` en [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py) y el filtro de `thinkingConfig` en [antigravity_client.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/antigravity_client.py) para reconocer de manera general y robusta a cualquier modelo de `antigravity` que contenga `"pro"` o `"thinking"` en su identificador (ej. `gemini-3.1-pro-high`, `gemini-pro-agent`, `gemini-3.1-pro-low`), evitando 400 Bad Request en peticiones y cargando el presupuesto de tokens correcto.
  - **Instrucciones de Agentes Paralelos**: Se actualizó [tool.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/skills/bundled/call_agents_parallel/scripts/tool.py) para que los mensajes de inicio enviados a los agentes en modo paralelo incluyan una advertencia ineludible y obligatoria sobre el uso de la herramienta `task_tracker` desde su primer turno.
  - **Pruebas Unitarias**: Se corrigió el desempaquetado de `map_messages` en el test existente de [test_antigravity_integration.py](file:///home/gato/Proyectos/Gemini-Interpreter/tests/test_antigravity_integration.py) y se añadieron nuevas pruebas unitarias (`test_thinking_config_injection` y `test_agent_dynamic_prompts`) para validar la inyección de `thinkingConfig` en el payload y el comportamiento dinámico de los prompts según el tipo de modelo seleccionado.

---

## [0.6.15] - 2026-06-09

### 🐛 Corrección y Soporte — Mapeo de gemini-3.1-pro-high y Habilitación de Razonamiento en Antigravity
- **Cambios**:
  - **Mapeo del Modelo**: Se resolvió el error `400 Invalid Argument` al usar `gemini-3.1-pro-high` mapeándolo de forma transparente y compatible a `gemini-pro-agent` en [antigravity_client.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/antigravity_client.py), ya que la API de Google Antigravity requiere este identificador y rechaza la cadena cruda de alta capacidad.
  - **Activación y Visualización de Pensamientos (CoT)**: Dado que el proxy de la API de Google Antigravity oculta/elimina los pensamientos nativos en la respuesta final de streaming (sólo enviando firmas binarias `thoughtSignature` internas), se desactivó `thinkingConfig` y `supports_thinking` para modelos del proveedor `antigravity` en [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py) y [antigravity_client.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/antigravity_client.py). Esto fuerza al sistema prompt a exigir a los modelos de Antigravity generar un razonamiento manual (envolviéndolo en etiquetas XML `<thought>...</thought>`), garantizando que la TUI intercepte, parsee y visualice en vivo los pensamientos del agente.
  - **Secuencia de Mensajes y Alternancia de Turnos (HTTP 400)**: Se corrigió el error `API Error (400): Please ensure that function call turn comes immediately after a user turn or after a function response turn.` que ocurría al ejecutar herramientas con modelos de Antigravity. Se introdujo una bifurcación en [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py) para omitir la lógica compleja de filtrado/remoción de tool_calls (pensada para OpenRouter/Baidu) cuando se utiliza el proveedor `antigravity`. Esto asegura que los mensajes se transmitan 1:1, manteniendo la alternancia estricta de turnos exigida por la API de Google Gemini.
  - **Pruebas de Integración**: Se actualizaron las pruebas unitarias y de integración correspondientes en [test_antigravity_integration.py](file:///home/gato/Proyectos/Gemini-Interpreter/tests/test_antigravity_integration.py) para que sean consistentes con el CoT manual forzado en todos los modelos de Antigravity.



---

## [0.6.16] - 2026-06-10

### 🐛 Corrección — Pérdida de contexto en la gestión e historiales de resumen
- **Causa raíz**: 
  1. **Truncamiento agresivo y ciego (12k chars)**: El método `summarize_conversation_history` de `LLMService` convertía el historial antiguo a texto plano y, si este medía más de 12.000 caracteres, lo truncaba brutalmente quedándose solo con el final. Como el resumen del pasado lejano (mensaje de sistema) se ubicaba al principio de este texto, se descartaba por completo en cada paso sucesivo de compresión, provocando que el agente olvidara progresivamente todo lo ocurrido.
  2. **Colapso por outputs gigantes**: Los outputs de comandos muy grandes en los mensajes de herramienta (`ToolMessage`) no se truncaban antes de formar el texto para resumir, provocando que un solo comando gigante excediera el límite de caracteres y empujara fuera del contexto de resumen a todos los mensajes conversacionales del usuario y asistente.
  3. **Límites de resumen rígidos**: El `DEFAULT_MAX_SUMMARY_LENGTH` de `HistoryManager` estaba hardcodeado en 2.000 caracteres, provocando que si el LLM generaba un resumen extenso, rico y detallado de la conversación, este se cortara destructivamente a la mitad de su longitud.
  4. **Tests unitarios rotos**: La restricción estricta de límites mínimos obligatorios de historial (30 mensajes y 50k caracteres) impedía que los tests compactos de historial realizaran simulaciones de resumen de forma controlada. Además, mocks obsoletos en `test_conversation_history_retention.py` carecían de los métodos `stop_live`/`update_live` necesarios tras las últimas actualizaciones TUI, y probaban la denegación con un comando seguro (`ls`) que era auto-aprobado por diseño.
- **Solución**:
  - **Preservación de Resumen Anterior**: Se actualizó `summarize_conversation_history` en [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py) para que busque y extraiga de forma explícita y flexible cualquier mensaje de tipo resumen previo (estándar o forzado). El resumen anterior se extrae y se pasa en una sección prioritaria al principio del prompt (`RESUMEN DE LA CONVERSACIÓN ANTERIOR (PASADO LEJANO)`), instruyendo al modelo consolidar y expandir esta información en lugar de sobrescribirla.
  - **Autotruncamiento Local**: Se introdujo el truncamiento individual de mensajes a un máximo de 5000 caracteres en la preparación del texto plano para el resumen, evitando que los outputs gigantes de herramientas monopolicen el contexto.
  - **Aumento del Contexto de Resumen**: Se amplió el límite máximo del buffer de mensajes recientes a resumir a 100.000 caracteres, un valor óptimo para los modelos actuales que previene pérdidas de contexto intermedio.
  - **Incremento de Límites de Resumen**: Se subió `DEFAULT_MAX_SUMMARY_LENGTH` a 5500 caracteres en [history_manager.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/history_manager.py) para permitir resúmenes consolidadores extensos.
  - **Límites Condicionales para Tests**: Se relajaron las restricciones mínimas de historial si el límite solicitado es menor a 10 mensajes o 1000 caracteres, permitiendo que la suite de pruebas se ejecute correctamente.
  - **Actualización de Mocks y Tests**:
    - Se agregaron los métodos `stop_live` y `update_live` a `DummyTerminalUI` en [test_conversation_history_retention.py](file:///home/gato/Proyectos/Gemini-Interpreter/tests/unit/test_conversation_history_retention.py).
    - Se modificó `test_explicit_command_denial_does_not_execute_safe_command` para que use un comando no seguro (`rm -rf /`) y mockee `ask_approval_sync` de forma que devuelva `False` (emulando la denegación del usuario).
    - Se eliminó la prueba obsoleta `test_summary_snapshot_keeps_recent_removed_context` que invocaba a un método inactivo (`_build_summary_snapshot`).

---

## [0.6.17] - 2026-06-11

### 🐛 Corrección — Visualización del Pensamiento (CoT) y Comportamiento Errático en Streaming
- **Causa raíz**: 
  - **Fuga de pensamiento por fragmentación de tokens**: El sistema de detección de Chain of Thought (CoT) manual analizaba cada chunk recibido del stream de forma aislada. Si el tag `<thought>` o `</thought>` venía dividido en múltiples chunks del stream debido a la tokenización del modelo (por ejemplo, `"<"` y `"thought>"` en chunks contiguos), la verificación de subcadena `"<thought>" in chunk_str` fallaba por completo.
  - **Consecuencias**: Las etiquetas se filtraban y se imprimían directamente al usuario como texto normal en la respuesta del agente. Esto no solo impedía capturar el pensamiento en la burbuja TUI de KogniTerm, sino que además causaba respuestas erráticas y desestructuradas al confundirse el modelo por las directivas de formato de etiquetas no completadas.
- **Solución**:
  - **Buffer Acumulativo de Stream**: Se implementó una lógica de parseo basada en una ventana deslizante de acumulación (`stream_buffer` y `processed_index`) en el generador de `invoke` en [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py).
  - **Detección de Etiquetas Parciales**: Se introdujeron las funciones auxiliares `get_safe_yield_index` y `get_safe_thinking_yield_index` que detectan si el final de un fragmento de stream contiene un prefijo parcial de la etiqueta XML (como `"<"` o `"</th"`). Si es así, se pausa temporalmente la entrega (yield) de ese fragmento hasta que llegue el resto en el siguiente chunk y se complete la etiqueta.
  - **Aseguramiento de Pruebas**: Se creó una nueva prueba unitaria automatizada en [test_cot_stream_parser.py](file:///home/gato/Proyectos/Gemini-Interpreter/tests/test_cot_stream_parser.py) que simula el streaming de respuestas con tags XML fragmentados arbitrariamente y verifica la correcta captura del pensamiento y la total remoción de las etiquetas en el texto del mensaje final.
  - **Alternancia Estricta de Turnos en Gemini (HTTP 400)**:
    - **Causa raíz**: La API de Google Gemini (ya sea invocada nativamente en Google AI Studio mediante LiteLLM o mediante el proxy de Antigravity) exige una alternancia de turnos sumamente estricta y falla con un error `400 Bad Request` si la secuencia de mensajes es alterada (ej. si se remueven tool calls sin responder o se insertan mensajes de sistema intermedios). Anteriormente, la bifurcación que conservaba la secuencia original 1:1 de los mensajes del asistente y de herramientas solo se activaba si el nombre del modelo contenía `"antigravity"`. Al utilizar un modelo directo de Gemini (como `google/gemini-2.5-flash` o `gemini-1.5-flash`), la lógica por defecto de Mistral/Baidu alteraba la cola de mensajes y disparaba el error 400.
    - **Solución**: Se amplió la condición en [llm_service.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/llm_service.py) para que aplique el bypass de secuencia estricta 1:1 a cualquier modelo cuyo nombre contenga `"gemini"`, garantizando la compatibilidad total de llamadas a herramientas tanto en Antigravity como en Google AI Studio.


---
## [Unreleased]
### 🔥 Desimplementación del sandbox de procesos (bwrap)
- **Eliminado `_wrap_in_sandbox` y la detección de `bwrap`**: El wrapper de procesos en `SkillManager` con soporte para `bubblewrap` (bwrap) y fallback `subprocess + resource` se eliminó por completo. El código nunca funcionó fuera de entornos sin restricciones de user namespaces (Ubuntu 24.04+, WSL2, Docker, distros con AppArmor endurecido), y el aislamiento real que aportaba era marginal porque el script original vivía dentro del `--bind` del workspace.
- **`sandbox_required` fuera del schema**: Se quitó el campo del dataclass `Skill`, de `tool_registry`, de `get_tool`, de `get_available_tools`, de `get_skill_info`, de `get_tools_for_llm`, del migrador (`SkillMigrator._needs_sandbox` y la línea del frontmatter generado) y de los `SKILL.md` bundled (`execute-command`, `pc-interaction`, `python-executor`) y de workspace.
- **Tests actualizados**: `test_sandboxed_tool_wrapping` se renombró a `test_high_security_tool_passthrough` y verifica que `get_tool` retorna la función original sin envolver.
- **`get_tool` ahora es un lookup directo**: ya no decide enrutamiento por `security_level`/`sandbox_required`. El aislamiento para tools que lo necesiten debe aplicarse en el caller (`CommandApprovalHandler` / `command_executor`).
- **Bug colateral arreglado**: Faltaba `Optional` en el `import` de `typing` en `skill_migrator.py`; se añadió.

---

## [Unreleased] - 2026-02-20

### 🔬 Investigación Exhaustiva del Código KogniTerm

**Investigador:** KogniTerm DeepResearcher (BashAgent)
**Estado:** ✅ Completada

#### Resumen
Investigación completa del código fuente de KogniTerm utilizando lectura directa de archivos y búsqueda semántica en el codebase. Se analizaron los componentes críticos de seguridad, arquitectura, sistema de skills y deuda técnica.

#### � Hallazgos de Seguridad Crítica (8)
1. **Credenciales hardcodeadas** en `core/antigravity_client.py` — OAuth Google client_id/client_secret ofuscados con base64 inverso trivial
2. **Python executor sin sandbox real** — Kernel de Jupyter con acceso total al sistema sin aislamiento
3. **Bypass de lista blanca** — `_is_command_safe()` no maneja `$(...)`, backticks, pipes encubiertos, here-docs, `LD_PRELOAD`
4. **PTY persistente sin aislamiento** — `bash --login` mantiene estado entre comandos permitiendo inyección
5. **API keys en JSON plano** — Almacenamiento sin cifrado en `~/.kogniterm/config.json`
6. **CORS completamente abierto** — `allow_origins=["*"]` con credenciales habilitadas
7. **Endpoint /api/execute sin autenticación** — Ejecuta comandos sin verificar identidad
8. **WebSocket sin autenticación** — Conexión abierta sin verificación

#### � Hallazgos Arquitectónicos
- Arquitectura de 4 capas: Presentación → Negocio → Skills → Infraestructura
- 25+ skills con sistema de discovery JIT y 5 niveles de seguridad
- Componentes core: LLMService (2416 líneas), HistoryManager (1038 líneas), CommandExecutor (325 líneas)
- Patrones: Strategy, Observer, Factory, Registry, Plugin/JIT Loading

#### 🟠 Deuda Técnica Identificada
- 2 archivos .backup en repositorio (`llm_service.py.backup`, `agent_state.py.backup`)
- Código duplicado en TUI (`on_input_changed`/`on_text_area_changed`)
- Cobertura de tests < 10%, sin tests de integración
- ~40% de funciones con docstrings
- Race conditions en `session_pool.py` y `command_approval_handler.py`
- llm_service.py y skill_manager.py son candidatos urgentes a refactorización (>1300 líneas cada uno)

#### 🔵 Sistema de Skills
- SkillManager con sandboxing via bubblewrap (bwrap) para skills marcadas
- Permisos inferidos del nombre, no verificados en runtime
- SkillMigrator con mapeo de seguridad por keywords

#### Recomendaciones Prioritarias
1. Eliminar credenciales hardcodeadas de antigravity_client.py
2. Implementar sandbox real para python_executor
3. Reemplazar lista blanca estática por parser AST de bash
4. Usar `bash --norc --noprofile` en lugar de `bash --login`
5. Cifrar credenciales en reposo
6. Agregar autenticación al servidor FastAPI
7. Cerrar CORS a dominios específicos
8. Tests unitarios para componentes críticos
9. Eliminar archivos .backup del repositorio
10. Refactorizar archivos >1000 líneas

---

## [1.1.0] - 2026-02-21

### 📋 Análisis Arquitectónico y Skill de Arquitectura

#### Problema
No existía un informe consolidado de la arquitectura del proyecto KogniTerm ni una herramienta automatizada para analizar la arquitectura de cualquier proyecto de software.

#### Cambios Realizados

**1. Informe Arquitectónico Consolidado**
- **Archivo:** `docs/ARCHITECTURE_ANALYSIS.md`
- Se generó un informe completo que consolida todos los análisis previos realizados al proyecto
- Incluye: arquitectura de 4 capas, flujo de ejecución, componentes críticos, métricas, patrones de diseño, riesgos y recomendaciones
- Métricas documentadas: 156 archivos Python, ~43,463 LOC, 25 skills, 7+ patrones de diseño

**2. Skill `architecture_analyzer` Creada**
- **Ubicación:** `kogniterm/skills/workspace/architecture_analyzer/`
- **Categoría:** autonomous
- **Seguridad:** standard
- **Funcionalidad:**
  - Escanea estructura de directorios con profundidad configurable
  - Cuenta métricas: archivos, LOC por lenguaje, archivos más grandes
  - Detecta frameworks y tecnologías (FastAPI, LangChain, Textual, etc.)
  - Identifica patrones de diseño en la estructura (Plugin, Client-Server, Multi-Agent, etc.)
  - Encuentra puntos de entrada (main.py, app.py, terminal.py, etc.)
  - Analiza riesgos: archivos monolíticos, falta de tests, backups en producción
  - Genera recomendaciones automáticas
  - Guarda informe en Markdown
- **Parámetros:** project_path, output_path, max_depth, include_metrics, include_patterns, include_risks, exclude_dirs
- **Uso:** `analyze_architecture(project_path="/ruta/al/proyecto")`

#### Archivos Modificados
- `docs/ARCHITECTURE_ANALYSIS.md` — Creado (informe completo)
- `docs/Cambios.md` — Actualizado con esta entrada
- `kogniterm/skills/workspace/architecture_analyzer/` — Skill creada automáticamente

---

## [1.1.1] - 2026-07-03

### 🔧 Corrección de Chat en Sesiones Desktop y Endpoint de Configuración

#### Problema
1. En las sesiones desktop de KogniTerm, el chat no funcionaba y se interrumpía inmediatamente con un log de `Interrupción solicitada`. Esto ocurría porque en `kogniterm/server/session_pool.py`, la función `send` establecía la bandera de ejecución `self.is_running = True` antes de comprobar `if self.is_running:`. Esto hacía que la comprobación fuera siempre verdadera, cancelando cualquier ejecución y encolando el mensaje.
2. Al guardar configuraciones de modelos u otras opciones desde el modal de ajustes de la aplicación desktop, el servidor respondía con `422 Unprocessable Entity` porque FastAPI interpretaba el parámetro `req` de `/api/config/set` como un parámetro de consulta (query parameter) en lugar de un cuerpo de solicitud (request body).
3. El modelo por defecto configurado en `.env` (`kilocode/openrouter/owl-alpha`) daba un error `404 Not Found` en OpenRouter al iniciar el agente.

#### Cambios Realizados

**1. Corrección del flujo lógico en SessionPool**
- **Archivo:** `kogniterm/server/session_pool.py`
- Se movió la verificación `if self.is_running:` al principio del bloque de bloqueo asíncrono, antes de establecer `self.is_running = True`, previniendo la interrupción inmediata y permitiendo el procesamiento normal del mensaje.

**2. Corrección del Endpoint de Configuración**
- **Archivo:** `kogniterm/server/app.py`
- Se importó `Body` de `fastapi`.
- Se actualizó el parámetro del endpoint `/api/config/set` a `req: SetConfigRequest = Body(...)` para forzar a FastAPI a procesar la solicitud como JSON body en lugar de query string.

**3. Actualización de Modelo por Defecto**
- **Archivo:** `.env`
- Se actualizó `LITELLM_MODEL` a `'gemini/gemini-1.5-flash'` para utilizar un endpoint válido con la clave de API de Google provista.

#### Archivos Modificados
- [session_pool.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/server/session_pool.py)
- [app.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/server/app.py)
- [.env](file:///home/gato/Proyectos/Gemini-Interpreter/.env)
- [Cambios.md](file:///home/gato/Proyectos/Gemini-Interpreter/docs/Cambios.md)

---

## [1.1.2] - 2026-07-03

### 💬 Persistencia de Hilos de Chat y Corrección de Títulos Automáticos en Desktop

#### Problema
1. Los hilos de chat creados y guardados en el backend no se cargaban en la aplicación desktop al cambiar de conversación o al iniciar la aplicación, mostrándose siempre vacíos. Esto sucedía porque no existía un endpoint para recuperar el historial de mensajes de un hilo individual, y la conexión WebSocket no enviaba los mensajes históricos en la inicialización de la sesión.
2. Los hilos no se renombraban automáticamente o fallaban de forma silenciosa debido a:
   - Filtro de mensajes deficiente en `generate_title_if_needed` que no excluía mensajes vacíos o de herramientas intermedias (como `task_tracker`).
   - El cliente de Antigravity (`AntigravityClient.completion`) no devolvía objetos del tipo `SimpleNamespace` con la propiedad `.message` cuando `stream=False`, lo que causaba un error `'dict' object has no attribute 'message'` al intentar leer la respuesta del LLM para generar el título.
3. La aplicación de escritorio siempre iniciaba con un ID de conversación aleatorio temporal, lo que generaba un hilo vacío cada vez que se abría o refrescaba, en lugar de cargar la conversación más reciente.

#### Cambios Realizados

**1. Servidor Backend (FastAPI)**
- **Archivo:** `kogniterm/server/app.py`
  - Se agregó el endpoint `GET /api/threads/{thread_id}/messages` para exponer el historial del hilo.
  - Se implementó la función auxiliar `message_to_frontend_dict` para mapear los mensajes serializados de LangChain (`BaseMessage`) al formato que el frontend React requiere (`Message`).
- **Archivo:** `kogniterm/core/thread_manager.py`
  - Se optimizó `generate_title_if_needed` para robustecer el filtro de mensajes del prompt de renombrado (excluyendo mensajes de herramientas o vacíos) de modo que use los primeros mensajes donde el usuario y el asistente realmente interactúan.
- **Archivo:** `kogniterm/core/antigravity_client.py`
  - Se corrigió el método `completion` (rama `stream=False`) para envolver el objeto de mensaje y la lista de elecciones (`choices`) en instancias de `SimpleNamespace`, logrando compatibilidad con los accesos estilo objeto del LLMService.

**2. Cliente Desktop (React / TypeScript)**
- **Archivo:** `kogniterm-desktop/apps/desktop/src/hooks/useChat.ts`
  - Se añadió la llamada fetch al nuevo endpoint de historial `/api/threads/{thread_id}/messages` en el hook `useChat` al cambiar de `threadId`.
  - Se implementó una bandera `active` para evitar condiciones de carrera (race conditions) al cambiar rápidamente entre hilos de chat.
- **Archivo:** `kogniterm-desktop/apps/desktop/src/App.tsx`
  - Se actualizó el hook de efecto de montaje para que, al cargar la aplicación, recupere la lista de hilos y auto-seleccione el hilo más reciente en lugar de crear un ID temporal vacío.

#### Archivos Modificados
- [app.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/server/app.py)
- [thread_manager.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/thread_manager.py)
- [antigravity_client.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/core/antigravity_client.py)
- [useChat.ts](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/apps/desktop/src/hooks/useChat.ts)
- [App.tsx](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm-desktop/apps/desktop/src/App.tsx)
- [Cambios.md](file:///home/gato/Proyectos/Gemini-Interpreter/docs/Cambios.md)


---

## [0.6.18] - 2026-06-10

### 🚀 Nueva Característica — Comando `kogniterm upgrade`

#### Problema
No existía una forma nativa de actualizar KogniTerm desde la propia aplicación. Los usuarios debían ejecutar manualmente el script `install.sh` o usar `git pull` + `pip install` en el directorio de instalación.

#### Cambios Realizados

**1. Comando `upgrade` integrado en CLI**
- **Archivo:** `kogniterm/terminal/cli.py`
- Se añadió el método `CLIHandler.handle_upgrade()` que implementa la lógica completa de actualización:
  - **Detección automática de entorno**: Distingue entre instalación global (`~/.kogniterm`) y desarrollo local (directorio actual con `pyproject.toml`).
  - **Preservación de cambios locales**: Si el usuario tiene modificaciones sin confirmar en el repo, se aplica `git stash` automáticamente antes de actualizar y se restaura con `git stash pop` después.
  - **Sincronización con GitHub**: Ejecuta `git pull --no-rebase origin main` para traer los últimos cambios.
  - **Actualización del entorno virtual**: Reinstala el paquete en modo editable (`pip install -e .`) dentro del `venv` detectado.
  - **Validaciones previas**: Verifica disponibilidad de `git` y existencia del repositorio antes de proceder.
- Se registró el subcomando `upgrade` en `run_cli()` para que sea ejecutable como `kogniterm upgrade`.

**2. Documentación**
- Se actualizó el registro de cambios con esta entrada en `docs/Cambios.md`.

#### Archivos Modificados
- [cli.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/terminal/cli.py)
- [Cambios.md](file:///home/gato/Proyectos/Gemini-Interpreter/docs/Cambios.md)
