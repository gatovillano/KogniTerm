FILE_CONTENT_START: project_structure.md
# Estructura del Proyecto KogniTerm

Aquí se describe la estructura del proyecto KogniTerm, basada en una exploración profunda de sus directorios y archivos.

## Contenido del Directorio Raíz

*   `image.png`: Archivo de imagen.
*   `README.md`: Documentación principal del proyecto.
*   `mermaid_diagram_1754863457462.png`: Diagrama generado con Mermaid.
*   `kogniterm_kernel.py`: Probablemente relacionado con el kernel de ejecución.
*   `kogniterm.egg-info/`: Metadatos de la distribución del paquete.
*   `kogniterm/`: Directorio principal de la aplicación KogniTerm.
*   `typescript/`: Directorio relacionado con TypeScript.
*   `kogniterm_history.json`: Historial de interacciones o comandos.
*   `pyproject.toml`: Configuración del proyecto y dependencias.
*   `project_structure.md`: Este mismo archivo de documentación de la estructura.
*   `src/`: Directorio para el código fuente.
*   `img_1757367894519.png`: Archivo de imagen.
*   `llm_context.md`: Archivo para la memoria contextual del LLM.
*   `docs/`: Documentación adicional.
*   `setup.py`: Script de configuración para la instalación.

## Directorio `kogniterm/`

Este es el directorio principal de la aplicación KogniTerm.

*   `main.py`: Punto de entrada principal de la aplicación.
*   `requirements.txt`: Dependencias del proyecto.
*   `core/`: Contiene la lógica central y los componentes principales de KogniTerm.
*   `terminal/`: Gestiona la interfaz y la interacción con la terminal.
*   `kogniterm.egg-info/`: Metadatos de la distribución del paquete.

## Directorio `kogniterm/core`

El corazón de KogniTerm, donde reside la inteligencia y la capacidad de acción.

*   `agents/`: Módulos que definen los diferentes agentes de KogniTerm.
*   `tools/`: Colección de herramientas que los agentes utilizan para interactuar con el sistema y la web.
*   `llm_service.py`: Servicio para interactuar con los modelos de lenguaje.
*   `llm_providers.py`: Define los proveedores de modelos de lenguaje.
*   `command_executor.py`: Módulo para la ejecución de comandos.
*   `google_tools_converter.py`: Un conversor para herramientas de Google.

### Dentro de `kogniterm/core/agents`

Aquí se definen los diferentes tipos de agentes que operan en KogniTerm.

*   `orchestrator_agent.py`: El agente encargado de orquestar y coordinar las tareas.
*   `bash_agent.py`: Un agente especializado en la ejecución de comandos bash.

### Dentro de `kogniterm/core/tools`

Este directorio contiene una amplia gama de herramientas que extienden las capacidades de KogniTerm.

*   `web_fetch_tool.py`: Para obtener el contenido HTML de una URL.
*   `execute_command_tool.py`: Para ejecutar comandos bash.
*   `file_operations_tool.py`: Operaciones CRUD básicas en archivos y directorios.
*   `file_create_tool.py`: Creación de archivos.
*   `file_read_tool.py`: Lectura de archivos.
*   `file_delete_tool.py`: Borrado de archivos.
*   `file_update_tool.py`: Actualización de archivos.
*   `file_read_directory_tool.py`: Listado de contenido de directorios.
*   `file_read_recursive_directory_tool.py`: Listado recursivo de contenido de directorios.
*   `file_search_tool.py`: Búsqueda de archivos.
*   `memory_init_tool.py`: Inicialización de la memoria contextual.
*   `memory_read_tool.py`: Lectura de la memoria contextual.
*   `memory_append_tool.py`: Añadir contenido a la memoria contextual.
*   `memory_summarize_tool.py`: Resumen de la memoria contextual.
*   `brave_search_tool.py`: Para realizar búsquedas en la web (requiere API Key).
*   `web_scraping_tool.py`: Para extraer datos estructurados de HTML.
*   `python_executor.py`: Para ejecutar código Python.
*   `github_tool.py`: Para interactuar con repositorios de GitHub.
*   `set_llm_instructions_tool.py`: Para establecer instrucciones al LLM.

## Directorio `kogniterm/terminal`

Gestioma la interfaz de usuario y la interacción directa a través de la terminal.

*   `__init__.py`: Inicialización del paquete Python.
*   `__pycache__/`: Caché de bytecode de Python.
*   `agent_interaction_manager.py`: Gestiona las interacciones con los agentes.
    *   **Propósito**: Orquesta el flujo de interacción entre el usuario y el agente de IA (específicamente, el agente bash).
    *   **Funcionalidad Clave**:
        *   Inicializa el `LLMService` y el `AgentState`.
        *   Crea y gestiona el agente bash.
        *   Asegura que el `SYSTEM_MESSAGE` esté siempre al inicio del historial de mensajes.
        *   El método `invoke_agent(user_input)` procesa la entrada del usuario, la añade al historial, invoca al agente bash, actualiza el `AgentState` con la respuesta del agente y guarda el historial. También extrae `command_to_confirm` si el agente sugiere un comando.
    *   **Rol en el Sistema**: Actúa como el puente entre la entrada cruda del usuario y el procesamiento del agente de IA, gestionando el estado del agente y el historial de mensajes.
*   `command_approval_handler.py`: Maneja la aprobación de comandos.
    *   **Propósito**: Gestiona el proceso de aprobación de comandos generados por el agente de IA antes de su ejecución.
    *   **Funcionalidad Clave**:
        *   Recupera el `tool_call_id` del último `AIMessage` para asociar la respuesta.
        *   Genera una explicación en lenguaje natural del comando propuesto utilizando el `LLMService`.
        *   Muestra el comando y su explicación al usuario a través de `TerminalUI`.
        *   Solicita la aprobación del usuario (a menos que el modo `auto_approve` esté activado).
        *   Si se aprueba, ejecuta el comando utilizando `CommandExecutor` y captura su salida.
        *   Añade un `ToolMessage` al historial del agente con la salida del comando o un mensaje de cancelación.
        *   Guarda el historial actualizado.
    *   **Rol en el Sistema**: Proporciona una capa crucial de seguridad y transparencia, permitiendo a los usuarios revisar y aprobar comandos potencialmente impactantes antes de que se ejecuten en su sistema.
*   `kogniterm_app.py`: Aplicación principal de KogniTerm para la terminal.
    *   **Propósito**: La clase principal de la aplicación que orquesta todos los componentes de la interfaz de terminal de KogniTerm.
    *   **Funcionalidad Clave**:
        *   Inicializa `LLMService`, `CommandExecutor`, `AgentState`, `TerminalUI`, `MetaCommandProcessor`, `AgentInteractionManager` y `CommandApprovalHandler`.
        *   Configura `PromptSession` con `FileHistory` y un `FileCompleter` para sugerencias de rutas de archivos.
        *   Define atajos de teclado personalizados para el prompt.
        *   El método `run()` es el bucle principal de la aplicación:
            *   Muestra un banner de bienvenida.
            *   Solicita continuamente la entrada del usuario.
            *   Procesa meta-comandos (ej. `%salir`, `%reset`) a través de `MetaCommandProcessor`.
            *   Invoca al agente mediante `AgentInteractionManager`.
            *   Si un comando requiere confirmación, llama a `CommandApprovalHandler`.
            *   Maneja y muestra la salida estructurada de `PythonTool` y `FileOperationsTool`.
            *   Gestiona el estado del agente y guarda el historial de la conversación.
    *   **Rol en el Sistema**: Es el centro neurálgico que une todos los demás módulos del directorio `terminal`, gestionando el flujo general de interacción del usuario y el ciclo de vida de la aplicación.
*   `meta_command_processor.py`: Procesa meta-comandos.
    *   **Propósito**: Gestiona comandos especiales (meta-comandos) que controlan la propia aplicación KogniTerm, en lugar de ser pasados al agente de IA.
    *   **Funcionalidad Clave**:
        *   La clase `MetaCommandProcessor` inicializa con `LLMService`, `AgentState` y `TerminalUI`.
        *   El método `process_meta_command(user_input)` comprueba comandos como `%salir`, `%reset`, `%undo`, `%help` y `%compress`.
            *   `%salir`: Termina la aplicación.
            *   `%reset`: Reinicia el estado del agente y el historial de conversación, re-añadiendo el mensaje del sistema.
            *   `%undo`: Elimina la última respuesta de IA y la entrada del usuario del historial.
            *   `%help`: Muestra los meta-comandos disponibles.
            *   `%compress`: Resume el historial de conversación utilizando el `LLMService` y lo reemplaza con el resumen.
    *   **Rol en el Sistema**: Proporciona control directo sobre el estado y el comportamiento de la aplicación, ofreciendo funciones de utilidad al usuario.
*   `terminal.py`: Módulo principal para la gestión de la terminal.
    *   **Propósito**: Actúa como el punto de entrada principal para la aplicación de terminal de KogniTerm, conteniendo la función `main`. También define la clase `FileCompleter`.
    *   **Funcionalidad Clave**:
        *   La clase `FileCompleter` proporciona autocompletado para rutas de archivos cuando el usuario escribe `@`, utilizando `FileOperationsTool` para listar directorios de forma recursiva.
        *   La función `main()` crea una instancia de `KogniTermApp` y llama a su método `run()`.
    *   **Rol en el Sistema**: Sirve como el iniciador de la aplicación de terminal y proporciona la lógica de autocompletado de archivos.
*   `terminal_ui.py`: Componentes de la interfaz de usuario de la terminal.
    *   **Propósito**: Gestiona todos los aspectos de la interfaz de usuario en la terminal, utilizando la biblioteca `rich` para una salida mejorada.
    *   **Funcionalidad Clave**:
        *   La clase `TerminalUI` inicializa con un objeto `rich.Console`.
        *   `print_message(message, style)`: Imprime mensajes con estilo en la consola.
        *   `print_welcome_banner()`: Muestra un banner de bienvenida visualmente atractivo para KogniTerm.
        *   `_format_text_with_basic_markdown(text)`: Una función auxiliar (ubicada en el mismo archivo) que aplica formato Markdown básico (negritas, bloques de código) utilizando `rich.Text` y `rich.Syntax` para una presentación mejorada.
    *   **Rol en el Sistema**: Responsable de toda la salida presentada al usuario, asegurando una experiencia de terminal clara, legible y visualmente atractiva.

---

### Ideas para un Nuevo Agente (Inspirado en OpenInterpreter)

Con esta comprensión de la estructura de KogniTerm, podemos empezar a pensar en cómo integrar un nuevo agente similar a OpenInterpreter. Este agente podría:

*   Utilizar el `python_executor.py` y el `execute_command_tool.py` para interactuar con el sistema.
*   Aprovechar las herramientas de `file_operations` para la gestión de archivos.
*   Coordinarse a través del `orchestrator_agent.py`.
*   Extender las capacidades de interacción con el usuario a través del módulo `terminal`.

¡Esta base nos será muy útil para el diseño!

---

### Análisis Detallado de `kogniterm/core/command_executor.py`

#### 📂 `command_executor.py`
*   **Propósito**: Ejecuta comandos bash en un pseudo-terminal (PTY), permitiendo la comunicación interactiva y la captura de salida en tiempo real, así como el reenvío de la entrada del usuario.
*   **Funcionalidad Clave**:
    *   **Ejecución Interactiva con PTY**: Utiliza `pty.openpty()` para crear un pseudo-terminal, lo que permite que los comandos se ejecuten como si estuvieran en una terminal real, manejando correctamente la entrada y salida interactiva (incluyendo solicitudes de contraseña para `sudo`).
    *   **Modo "Raw" de Terminal**: Configura la terminal del usuario en modo "raw" (`tty.setraw`), lo que significa que todas las pulsaciones de teclas se envían directamente al proceso del comando sin procesamiento intermedio por parte de la terminal.
    *   **Manejo de `sudo`**: Si el comando comienza con `sudo`, lo envuelve con `script -qc` para asegurar que las solicitudes de contraseña se manejen correctamente dentro del PTY.
    *   **Bucle de E/S con `select`**: Un bucle principal utiliza `select.select()` para monitorear simultáneamente la salida del comando (desde el PTY) y la entrada del usuario (desde `stdin`).
    *   **Salida en Tiempo Real**: La salida del comando se lee en bloques y se cede (`yields`) en tiempo real, lo que permite a KogniTerm mostrar la progresión del comando al usuario.
    *   **Entrada del Usuario**: La entrada del usuario se lee desde `stdin` y se escribe directamente en el PTY del comando.
    *   **Cancelación de Comando**: Permite al usuario cancelar un comando en ejecución presionando la tecla `ESC`.
    *   **Restauración de la Terminal**: **Críticamente**, asegura que la configuración original de la terminal se restaure siempre, incluso si ocurren errores, para evitar dejar la terminal del usuario en un estado inutilizable.
    *   **Terminación de Procesos**: El método `terminate()` envía una señal `SIGTERM` al grupo de procesos del comando, permitiendo una terminación limpia.
*   **Rol en el Sistema**: Es el motor que permite a KogniTerm interactuar directamente con el sistema operativo del usuario. Su diseño interactivo es crucial para comandos que requieren entrada del usuario o que producen salida progresiva, como instalaciones o scripts interactivos.
:FILE_CONTENT_END