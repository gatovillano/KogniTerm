---
## 29-09-25 Corrección de AttributeError en LLMService
Descripción general: Se corrigió un `AttributeError` en la clase `LLMService` donde se intentaba llamar a un método `_convert_messages_to_litellm_format` que no existía.

- **Punto 1**: Se reemplazó la llamada a `self._convert_messages_to_litellm_format(messages)` por `[_to_litellm_message(msg) for msg in messages]` en la línea 647 de `kogniterm/core/llm_service.py`.
- **Punto 2**: Se corrigió la asignación de `litellm_messages` después del truncamiento de mensajes conversacionales, reemplazando `self._convert_messages_to_litellm_format(messages)` por `all_initial_system_messages_for_llm + current_conversational_messages` en la línea 599 de `kogniterm/core/llm_service.py`.
---
## 29-09-25 Limpieza de la lógica de contexto para refactorización
Descripción general: Se ha eliminado toda la lógica de gestión de contexto de los módulos en `kogniterm/core/context/` para preparar una nueva implementación mejorada y óptima.

- **Punto 1**: Contenido de `kogniterm/core/context/config_file_analyzer.py` vaciado.
- **Punto 2**: Contenido de `kogniterm/core/context/context_indexer.py` vaciado.
- **Punto 3**: Contenido de `kogniterm/core/context/context_orchestrator.py` vaciado.
- **Punto 4**: Contenido de `kogniterm/core/context/file_search_module.py` vaciado.
- **Punto 5**: Contenido de `kogniterm/core/context/file_system_watcher.py` vaciado.
- **Punto 6**: Contenido de `kogniterm/core/context/folder_structure_analyzer.py` vaciado.
- **Punto 7**: Contenido de `kogniterm/core/context/git_interaction_module.py` vaciado.
- **Punto 8**: Contenido de `kogniterm/core/context/ignore_pattern_manager.py` vaciado.
- **Punto 9**: Contenido de `kogniterm/core/context/llm_context_builder.py` vaciado.
- **Punto 10**: Contenido de `kogniterm/core/context/path_manager.py` vaciado.
- **Punto 11**: Contenido de `kogniterm/core/context/project_context_initializer.py` vaciado.
- **Punto 12**: Contenido de `kogniterm/core/context/workspace_context.py` vaciado.
---
## 29-09-25 Eliminación de archivos de la lógica de contexto
Descripción general: Se han eliminado físicamente todos los archivos de la carpeta `kogniterm/core/context/` después de limpiar todas sus referencias en el resto del proyecto, preparando el terreno para una nueva implementación de la lógica de contexto.

- **Punto 1**: Se eliminaron las importaciones y el código dependiente de los módulos de contexto en:
    *   `kogniterm/core/tools/github_tool.py`
    *   `kogniterm/core/tools/memory_read_tool.py`
    *   `kogniterm/core/tools/file_read_tool.py`
    *   `kogniterm/core/tools/memory_init_tool.py`
    *   `kogniterm/core/tools/python_executor.py`
    *   `kogniterm/core/tools/memory_summarize_tool.py`
    *   `kogniterm/core/tools/memory_append_tool.py`
    *   `kogniterm/terminal/terminal.py`
    *   `kogniterm/terminal/meta_command_processor.py`
    *   `kogniterm/terminal/kogniterm_app.py`
- **Punto 2**: Se eliminaron los siguientes archivos de la carpeta `kogniterm/core/context/`:
    *   `config_file_analyzer.py`
    *   `context_indexer.py`
    *   `context_orchestrator.py`
    *   `file_search_module.py`
    *   `file_system_watcher.py`
    *   `folder_structure_analyzer.py`
    *   `git_interaction_module.py`
    *   `ignore_pattern_manager.py`
    *   `llm_context_builder.py`
    *   `path_manager.py`
    *   `project_context_initializer.py`
    *   `workspace_context.py`
---
## 29-09-25 Implementación de WorkspaceContext y comando %init
Descripción general: Se implementó una nueva lógica para gestionar el contexto del espacio de trabajo (`WorkspaceContext`) que se inicializa bajo demanda mediante el comando `%init`. Esto permite al LLM acceder a la estructura de carpetas y al contenido de archivos específicos del proyecto de forma controlada.

- **Punto 1**: Se creó el archivo `kogniterm/core/context/workspace_context.py` con la clase `WorkspaceContext`. Esta clase es responsable de:
    - Obtener la estructura de carpetas del directorio raíz.
    - Leer el contenido de archivos especificados.
    - Construir un mensaje de sistema formateado con el contexto recopilado.
- **Punto 2**: Se modificó `kogniterm/core/llm_service.py` para integrar `WorkspaceContext`:
    - Se importó `WorkspaceContext`.
    - Se instanció `WorkspaceContext` en el método `__init__`.
    - Se inicializaron `self.workspace_context_initialized`, `self.console`, `self.max_history_messages` y `self.max_history_chars` en `__init__`.
    - Se modificó `_build_llm_context_message()` para que utilice la instancia de `WorkspaceContext` para obtener el mensaje de contexto.
    - Se añadió el método `initialize_workspace_context()` para activar la recopilación del contexto.
- **Punto 3**: Se modificó `kogniterm/terminal/meta_command_processor.py` para añadir el comando `%init`:
    - Se implementó la lógica para procesar el comando `%init`, que llama a `llm_service.initialize_workspace_context()`.
    - El comando `%init` ahora permite especificar archivos a incluir en el contexto (ej: `%init README.md,src/main.py`).
    - Se actualizó el mensaje de ayuda (`%help`) para incluir la descripción del nuevo comando `%init`.