# 📘 Manual Técnico y Filosófico de KogniTerm

## 1. Introducción y Espíritu 🌟

**KogniTerm** no es simplemente un asistente de terminal; es un **Entorno de Desarrollo Agéntico (ADE)** que reside en tu línea de comandos. Su objetivo es transformar la interacción solitaria entre el desarrollador y el sistema operativo en una colaboración dinámica con un equipo de agentes de IA especializados.

### Filosofía del Proyecto

El "espíritu" de KogniTerm se sustenta en tres pilares fundamentales:

1.  **Especialización sobre Generalización**: Un solo modelo de IA no puede ser experto en todo. KogniTerm orquesta un equipo de roles definidos (Investigador, Desarrollador, Operador) para abordar tareas complejas con mayor precisión.
2.  **Universalidad (The "Any-Model" Engine)**: KogniTerm democratiza el acceso a capacidades agénticas. Gracias a su **Motor de Parseo Híbrido**, otorga la capacidad de usar herramientas ("Tool Calling") a modelos que nativamente no la soportan (como Llama 3 o DeepSeek base), interpretando sus intenciones directamente desde el lenguaje natural.
3.  **Transparencia y Control (Human-in-the-Loop)**: La IA es una herramienta, no el piloto. KogniTerm está diseñado con la seguridad como prioridad: ninguna acción destructiva (borrar archivos, ejecutar comandos peligrosos) ocurre sin la confirmación explícita del usuario.

---

## 2. Características Técnicas ⚙️

### 🧠 Arquitectura Multi-Agente
KogniTerm implementa un sistema jerárquico donde un agente principal (**BashAgent**) actúa como orquestador, delegando tareas de investigación a un **ResearcherAgent** o tareas de codificación a un **CodeAgent**. Esto aísla contextos y responsabilidades.

### 🔌 Motor de Parseo Universal (`LLMService`)
El corazón de KogniTerm es su capacidad para "entender" cualquier LLM.
*   **Soporte Nativo**: Utiliza APIs oficiales de `tool_calls` para OpenAI, Gemini y Anthropic.
*   **Text-to-Tool Parsing**: Para modelos open-source o locales, KogniTerm analiza el texto generado en busca de patrones (JSON, XML, bloques de código) y los convierte en ejecuciones de herramientas estructuradas.

### 📚 RAG Local (Retrieval-Augmented Generation)
KogniTerm indexa tu base de código localmente utilizando **ChromaDB**. Esto permite a los agentes realizar búsquedas semánticas ("¿Dónde está la lógica de autenticación?") en lugar de simples búsquedas de texto, proporcionando un contexto profundo y relevante.

### 🛡️ Sandbox de Ejecución
Los comandos de shell se ejecutan en un entorno controlado (`CommandExecutor`) que captura la salida estándar y de error en tiempo real, permitiendo a los agentes reaccionar ante fallos o solicitar input al usuario.

---

## 3. Funciones Detalladas (Una a Una) 🛠️

### A. Comandos Mágicos (Meta-Comandos)
Estos comandos controlan el entorno de KogniTerm y no son enviados al LLM.

*   **`%models`**: Abre un menú interactivo TUI para cambiar el modelo de IA activo en tiempo real.
*   **`%help`**: Muestra un panel de ayuda navegable con atajos y descripciones.
*   **`%reset`**: Limpia el historial de conversación y el contexto de la sesión actual.
*   **`%undo`**: Revierte la última acción o mensaje del asistente (útil si el modelo alucina).
*   **`%compress`**: Resume el historial de la conversación para liberar tokens de contexto sin perder información clave.
*   **`%keys`**: Muestra/Oculta las teclas de atajo disponibles en la barra inferior.
*   **`%history`**: Muestra el historial completo de la sesión actual.

### B. Herramientas del Agente (Tools)
Capacidades que los agentes pueden invocar para interactuar con el sistema.

1.  **`execute_command`**: Ejecuta comandos de shell (bash). Requiere aprobación para comandos con efectos secundarios.
2.  **`read_file`**: Lee el contenido completo de un archivo.
3.  **`write_file`**: Crea o sobrescribe un archivo completo.
4.  **`advanced_file_editor`**: Herramienta quirúrgica para editar archivos. Permite:
    *   `insert_line`: Insertar líneas en una posición específica.
    *   `replace_regex`: Reemplazar texto usando expresiones regulares.
    *   `append/prepend`: Añadir contenido al inicio o final.
5.  **`codebase_search`**: Realiza búsquedas semánticas en el índice RAG del proyecto.
6.  **`grep_search`**: Búsqueda de texto exacta usando `ripgrep` (si está disponible) o `grep`.
7.  **`list_directory`**: Lista el contenido de un directorio.
8.  **`call_agent`**: Permite a un agente delegar una subtarea a otro agente especializado (ej. BashAgent -> ResearcherAgent).
9.  **`ask_human`**: Permite al agente hacer una pregunta explícita al usuario para aclarar dudas.

### C. CLI de Gestión (`kogniterm`)
Comandos para configurar la aplicación desde la terminal del sistema.

*   **`kogniterm keys set <provider> <key>`**: Configura API keys (openai, google, openrouter).
*   **`kogniterm models use <model_id>`**: Selecciona el modelo por defecto.
*   **`kogniterm index .`**: Genera o actualiza el índice RAG del directorio actual.

---

## 4. Estructura y Arquitectura 🏗️

### Diagrama de Flujo (LangGraph)

El flujo de ejecución se basa en un grafo de estados cíclico:

1.  **Input Usuario**: El usuario introduce un comando o pregunta.
2.  **BashAgent (Nodo Principal)**: Analiza la entrada.
3.  **Decisión**:
    *   ¿Es un comando simple? -> Ejecuta directamente.
    *   ¿Es complejo? -> Genera un plan o delega.
4.  **Ejecución de Herramienta**: Si el agente decide usar una herramienta, el sistema intercepta la llamada.
5.  **Verificación (Human-in-the-Loop)**: Si la herramienta es sensible, se pide confirmación al usuario.
6.  **Resultado**: La salida de la herramienta vuelve al agente como una "observación".
7.  **Bucle**: El agente razona sobre la observación y decide el siguiente paso.

### Sistema de Memoria

KogniTerm maneja dos tipos de memoria:
1.  **Memoria de Corto Plazo (Session)**: El historial del chat actual, gestionado por `HistoryManager`.
2.  **Memoria de Largo Plazo (Context)**:
    *   **`llm_context.md`**: Archivo en `.kogniterm/` donde el agente puede guardar notas persistentes sobre el proyecto.
    *   **Vector DB (Chroma)**: Índice de embeddings del código para recuperación semántica.

---

## 5. Módulos del Sistema 📦

El código fuente se organiza en tres grandes bloques:

### 1. `kogniterm/core` (El Cerebro)
Contiene la lógica de negocio, los agentes y la inteligencia.

*   **`agents/`**: Definiciones de `BashAgent`, `ResearcherAgent`, `CodeAgent`.
*   **`tools/`**: Implementación de todas las herramientas (`execute_command`, `file_editor`, etc.).
*   **`llm_service.py`**: El motor de inferencia y parseo universal.
*   **`history_manager.py`**: Gestión del historial de conversación y persistencia.
*   **`command_executor.py`**: Sandbox para la ejecución de comandos de sistema.
*   **`context/`**: Lógica del sistema RAG e indexado (`embeddings_service.py`).

### 2. `kogniterm/terminal` (La Interfaz)
Maneja la interacción con el usuario y la presentación visual.

*   **`kogniterm_app.py`**: Punto de entrada de la aplicación.
*   **`terminal.py`**: Implementación de la UI con `prompt_toolkit`.
*   **`terminal_ui.py`**: Componentes visuales y renderizado de Markdown/Rich.
*   **`meta_command_processor.py`**: Lógica de los comandos mágicos (`%`).
*   **`command_approval_handler.py`**: Interfaz para la confirmación de comandos peligrosos.

### 3. `kogniterm/utils` (Utilidades)
Funciones auxiliares transversales.

*   Manejo de rutas, logging, formateo de texto y validaciones comunes.

---
*Documento generado automáticamente por el equipo de KogniTerm.*
