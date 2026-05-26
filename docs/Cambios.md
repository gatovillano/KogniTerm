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
- **Experiencia de instalación mejorada**: Se rediseñó por completo la interfaz del terminal para mostrar pasos numerados, barra de progreso interactiva, spinners animados durante tareas pesadas (como la instalación de pip y dependencias) y logs detallados guardados en `/tmp/kogniterm_install_[timestamp].log`.
- **Configuración de LLM interactiva**: Se agregó un nuevo paso interactivo que solicita al usuario seleccionar el proveedor de LLM (OpenAI, Groq, Google Gemini, Anthropic, Ollama, etc.), ingresar el modelo de preferencia y su API key, configurando automáticamente el archivo `.env` del proyecto.

---

## Versiones Anteriores

Para ver versiones anteriores a 0.4.3, consulta el historial de tags en GitHub:
```bash
git tag --sort=-version:refname
```
