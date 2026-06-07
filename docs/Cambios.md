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
