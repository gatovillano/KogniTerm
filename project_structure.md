# Estructura del Proyecto KogniTerm

Aquí se describe la estructura del proyecto KogniTerm, basada en una exploración profunda de sus directorios y archivos.

## Contenido del Directorio Raíz

*   `image.png`: Archivo de imagen.
*   `README.md`: Documentación principal del proyecto.
*   `mermaid_diagram_1754863457462.png`: Diagrama generado con Mermaid.
*   `kogniterm_kernel.py`: Probablemente relacionado con el kernel de ejecución.
*   `kogniterm.egg-info/`: Metadatos de la distribución del paquete.
*   `kogniterm/`: Directorio principal de la aplicación KogniTerm.
*   `build/`: Directorio de construcción.
*   `typescript/`: Directorio relacionado con TypeScript.
*   `kogniterm_history.json`: Historial de interacciones o comandos.
*   `pyproject.toml`: Configuración del proyecto y dependencias.
*   `project_structure.md`: Este mismo archivo de documentación de la estructura.
*   `src/`: Directorio para el código fuente.
*   `venv/`: Entorno virtual de Python.
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

Gestiona la interfaz de usuario y la interacción directa a través de la terminal.

*   `terminal.py`: Módulo principal para la gestión de la terminal.

---

### Ideas para un Nuevo Agente (Inspirado en OpenInterpreter)

Con esta comprensión de la estructura de KogniTerm, podemos empezar a pensar en cómo integrar un nuevo agente similar a OpenInterpreter. Este agente podría:

*   Utilizar el `python_executor.py` y el `execute_command_tool.py` para interactuar con el sistema.
*   Aprovechar las herramientas de `file_operations` para la gestión de archivos.
*   Coordinarse a través del `orchestrator_agent.py`.
*   Extender las capacidades de interacción con el usuario a través del módulo `terminal`.

¡Esta base nos será muy útil para el diseño!
