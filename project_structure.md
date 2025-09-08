# Estructura del Proyecto KogniTerm 🤖

Este documento describe la organización de archivos y directorios del proyecto KogniTerm, un intérprete de línea de comandos interactivo impulsado por LLMs.

## 📁 Directorio Raíz

*   `README.md`: Descripción general del proyecto, características, instalación y uso.
*   `kogniterm_kernel.py`: Archivo relacionado con el kernel del intérprete.
*   `kogniterm_history.json`: Historial de interacciones.
*   `llm_context.md`: Contexto de la memoria del LLM.
*   `setup.py`: Script de configuración para la instalación del paquete.
*   `mermaid_diagram_1754863457462.png`: Diagrama visual del proyecto.

## 📦 kogniterm/ (Directorio Principal de la Aplicación)

Este es el corazón de la aplicación KogniTerm.

*   `main.py`: Punto de entrada principal de la aplicación.
*   `requirements.txt`: Lista de dependencias de Python necesarias para el proyecto.
*   `__init__.py`: Marca el directorio como un paquete Python.

### 💻 kogniterm/terminal/

Contiene la lógica relacionada con la interfaz de la terminal.

*   `terminal.py`: Implementación de la interfaz de la terminal.
*   `__init__.py`: Marca el directorio como un paquete Python.

### 🧠 kogniterm/core/

Contiene la lógica central del sistema, servicios LLM, agentes y herramientas.

*   `command_executor.py`: Gestiona la ejecución de comandos.
*   `llm_service.py`: Servicio para interactuar con los modelos de lenguaje.
*   `tools.py`: Definiciones y orquestación de herramientas.
*   `__init__.py`: Marca el directorio como un paquete Python.

#### 🧑‍💻 kogniterm/core/agents/

Define los diferentes tipos de agentes que KogniTerm puede utilizar.

*   `orchestrator_agent.py`: Agente para la planificación y ejecución de tareas complejas.
*   `bash_agent.py`: Agente para la ejecución directa de comandos Bash.

#### 🛠️ kogniterm/core/tools/

Implementaciones de las diversas herramientas que KogniTerm puede utilizar.

*   `brave_search_tool.py`: Herramienta para realizar búsquedas web con Brave Search.
*   `execute_command_tool.py`: Herramienta para ejecutar comandos del sistema.
*   `file_operations_tool.py`: Herramienta para operaciones CRUD en archivos y directorios.
*   `github_tool.py`: Herramienta para interactuar con repositorios de GitHub.
*   `memory_append_tool.py`: Herramienta para añadir contenido a la memoria.
*   `memory_init_tool.py`: Herramienta para inicializar la memoria.
*   `memory_read_tool.py`: Herramienta para leer la memoria.
*   `memory_summarize_tool.py`: Herramienta para resumir la memoria.
*   `python_executor.py`: Herramienta para ejecutar código Python.
*   `web_fetch_tool.py`: Herramienta para obtener contenido HTML de una URL.
*   `web_scraping_tool.py`: Herramienta para extraer datos de páginas web.
*   `file_search_tool.py`: Herramienta para buscar archivos por patrón glob.
*   `__init__.py`: Marca el directorio como un paquete Python.

## 📚 docs/ (Documentación)

Contiene archivos de documentación adicionales.

*   `registro_errores_soluciones.md`: Registro de errores y soluciones.
*   `development_log.md`: Registro de desarrollo.
*   `flow_diagram.md`: Diagrama de flujo.
*   `gemini_cli_files.md`: Archivos relacionados con la CLI de Gemini.
*   `overview.md`: Vista general.
*   `modules.md`: Descripción de módulos.
*   `Cambios.md`: Registro de cambios.

## 🏗️ build/ (Artefactos de Construcción)

Contiene los archivos generados durante el proceso de construcción del paquete.

## 📦 kogniterm.egg-info/ (Metadatos del Paquete Python)

Contiene metadatos del paquete generados por `setuptools`.
