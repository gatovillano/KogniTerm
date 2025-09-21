---
## 17-09-2025 Corrección de Error "Missing corresponding tool call" en LiteLLM
**Descripción general:** Se corrigió el `APIConnectionError` (`Missing corresponding tool call for tool response message`) que ocurría al denegar la ejecución de un comando, especialmente con modelos de Google a través de LiteLLM.

-   **Punto 1**: Se modificó `CommandApprovalHandler` en `kogniterm/terminal/command_approval_handler.py` para que, al denegar un comando, se genere un `AIMessage` en lugar de un `ToolMessage`. Esto evita que LiteLLM busque un `tool_call` correspondiente que no existe en ese escenario.
-   **Punto 2**: Se reintrodujeron las líneas para guardar el historial y devolver el estado actualizado en `CommandApprovalHandler` que fueron eliminadas accidentalmente durante una refactorización previa.

---
## 18-09-2025 Corrección de SyntaxError en FileUpdateTool

**Descripción general:** Se corrigió un `SyntaxError` en la f-string de la herramienta `FileUpdateTool` que causaba un error de terminación de cadena.

-   **Punto 1**: Se modificó la línea 62 de [`kogniterm/core/tools/file_update_tool.py`](kogniterm/core/tools/file_update_tool.py:62) para asegurar que la f-string esté correctamente terminada, añadiendo `\n{colorized_diff_output}` dentro de la misma.
---
## 19-09-2025 Mejora de la Persistencia del Historial de Conversación

**Descripción general:** Se implementaron mejoras en el manejo del historial de conversación para asegurar su persistencia ante errores inesperados o cierres de la aplicación, evitando la pérdida de contexto.

-   **Manejo de Errores en Carga/Guardado ([`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py)):**
    -   Se añadió `traceback.print_exc()` en los bloques `except` de `_load_history` y `_save_history` para un registro más detallado de los errores de JSON y otras excepciones, facilitando la depuración sin alterar el comportamiento de retorno de historial vacío.
-   **Guardado Seguro al Salir ([`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py)):**
    -   Se implementó un bloque `finally` en el método `run()` de `KogniTermApp`. Esto garantiza que el historial (`self.llm_service._save_history(self.agent_state.messages)`) se guarde siempre antes de que la aplicación finalice, ya sea por una salida normal (ej. `Ctrl+D`), una `KeyboardInterrupt`, o cualquier excepción no manejada.
---
## 19-09-2025 Corrección de SyntaxError en KogniTermApp

**Descripción general:** Se corrigió un `SyntaxError` en el archivo [`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py) causado por un bloque `finally` mal posicionado.

-   **Reubicación de `finally`:** El bloque `finally` fue movido para envolver el bucle principal de la aplicación en el método `run()`, asegurando que el guardado del historial se ejecute correctamente al salir de la aplicación, independientemente de cómo termine la ejecución.
---
## 19-09-2025 Mejora de la Persistencia del Historial del LLM y Truncamiento con Resumen

**Descripción general:** Se implementaron mejoras en la persistencia del historial del LLM para soportar un historial por directorio de trabajo y se mejoró la estrategia de truncamiento para mantener un contexto más relevante.

-   **Persistencia por Directorio:**
    -   En [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py), se eliminaron las constantes `KOGNITERM_DIR` y `HISTORY_FILE` y se introdujo `self.history_file_path` como atributo de instancia.
    -   Se añadió el método `set_cwd_for_history(cwd: str)` en `LLMService` para establecer dinámicamente la ruta del archivo de historial basado en el directorio de trabajo actual y cargar/inicializar el historial correspondiente.
    -   En [`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py), se modificó el método `run()` para llamar a `self.llm_service.set_cwd_for_history(cwd)` cada vez que el directorio de trabajo cambia, asegurando que el historial cargado sea el correcto para la sesión actual.
    -   Se ajustó la inicialización de `self.agent_state.messages` en `KogniTermApp` para que siempre apunte a `self.llm_service.conversation_history`, manteniendo la coherencia.
-   **Truncamiento Inteligente con Resumen:**
    -   En [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py), se modificó el método `invoke` para que, antes de truncar el historial debido a límites de tamaño o mensajes, intente resumir la conversación utilizando `summarize_conversation_history()`. El resumen se inserta como un `SystemMessage` en el historial, manteniendo los mensajes más recientes para un contexto inmediato.
-   **Optimización del Guardado del Historial:**
    -   Se eliminó la llamada redundante a `self.llm_service._save_history(self.agent_state.messages)` de [`kogniterm/terminal/agent_interaction_manager.py`](kogniterm/terminal/agent_interaction_manager.py), ya que el guardado final y seguro se realiza en el bloque `finally` de `KogniTermApp.run()`.
---
## 19-09-2025 Corrección de "Missing corresponding tool call for tool response message" tras resumen de historial

**Descripción general:** Se abordó el error `litellm.APIConnectionError: Missing corresponding tool call for tool response message` que ocurría después del resumen del historial, causado por `ToolMessage`s huérfanos sin su `AIMessage` de invocación correspondiente.

-   **Filtrado de ToolMessages Huérfanos:**
    -   Se implementó una lógica de post-procesamiento en el método `invoke` de [`kogniterm/core/llm_service.py`](kogniterm/core/llm/llm_service.py). Esta lógica identifica y elimina `ToolMessage`s del historial que no tienen un `AIMessage` previo que haya solicitado esa herramienta (`tool_call`) en el historial reducido. Esto asegura la integridad del historial para `litellm` y evita el error.
---
## 19-09-2025 Persistencia del Historial entre Sesiones
52 | 
53 | **Descripción general:** Se aseguró que el historial de conversación del LLM persista entre diferentes sesiones de la aplicación, cargando el historial al inicio para el directorio de trabajo actual.
54 | 
55 | -   **Carga de Historial al Inicio:**
56 | 56 | 56 |     -   En el constructor de `KogniTermApp` en [`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py), se añadió una llamada inicial a `self.llm_service.set_cwd_for_history(initial_cwd)` para cargar el historial específico del directorio de trabajo actual al iniciar la aplicación.
57 | 57 | 57 |     -   Se modificó la inicialización de `self.agent_state = AgentState(messages=self.llm_service.conversation_history)` para que el estado del agente comience con el historial cargado, garantizando la continuidad de la conversación.
58 | 58 | 58 |     -   Se eliminó la lógica de detección de cambio de directorio dentro del bucle `run()` de `KogniTermApp`, ya que la carga del historial ahora se maneja al inicio de la sesión para el directorio de trabajo actual.
---
## 19-09-2025 Ajuste de Frecuencia de Resumen del Historial

**Descripción general:** Se ajustaron los límites del historial para reducir la frecuencia de los resúmenes, permitiendo conversaciones más largas antes de que se active la lógica de resumen.

-   **Aumento de Límites de Historial:**
    -   En [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py), se aumentaron los valores de `self.max_history_chars` de `60000` a `120000` y `self.max_history_messages` de `100` a `200`. Esto permite que el historial contenga más mensajes y caracteres antes de que se considere "demasiado largo" y se active el proceso de resumen.
---
## 19-09-2025 Mejora de la Calidad del Resumen del Historial

**Descripción general:** Se mejoró la calidad del resumen del historial, solicitando al modelo LLM un resumen más exhaustivo y detallado.

-   **Modificación del Prompt de Resumen:**
    -   En [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py), se modificó el `summarize_prompt` en el método `summarize_conversation_history()` para incluir instrucciones más explícitas al LLM, solicitando un resumen "EXHAUSTIVA, DETALLADA y EXTENSA" que capture todos los puntos clave, decisiones tomadas, tareas pendientes y cualquier información relevante, actuando como un reemplazo fiel del historial para la comprensión futura del LLM.
---
## 19-09-2025 Implementación del Módulo de Análisis de Archivos de Configuración

**Descripción general:** Se implementó un nuevo módulo para analizar archivos de configuración comunes (`package.json`, `tsconfig.json`, `.eslintrc.js`) y extraer información relevante del proyecto.

-   **Creación del Módulo:** Se creó el archivo [`kogniterm/core/context/config_file_analyzer.py`](kogniterm/core/context/config/config_file_analyzer.py) que contiene las funcionalidades para analizar diferentes tipos de archivos de configuración.
-   **Funcionalidades Implementadas:**
    -   `parsePackageJson(filePath: string): PackageJson`: Analiza `package.json` extrayendo dependencias, scripts, etc.
    -   `parseTsconfigJson(filePath: string): TsconfigJson`: Analiza `tsconfig.json` extrayendo configuraciones del compilador de TypeScript.
    -   `parseEslintrcJson(filePath: string): EslintrcJson`: Analiza `.eslintrc.js` (con una implementación simplificada para extraer configuraciones de JS).
-   **Definiciones de Tipos:** Se definieron `TypedDict` para `PackageJson`, `TsconfigJson` y `EslintrcJson` para tipado estático y mejor legibilidad.
---
## 19-09-2025 Implementación del Sistema de Gestión de Contexto de Proyectos en KogniTerm
Descripcion general: Se ha implementado un sistema robusto y eficiente de gestión de contexto de proyectos en KogniTerm, que permite al asistente comprender la estructura, configuración y estado de los proyectos en los que trabaja el usuario, y adaptar su comportamiento en consecuencia. Esto se logró a través de la creación e integración de varios módulos especializados.

-   **Clase WorkspaceContext**: Se implementó la clase [`WorkspaceContext`](kogniterm/core/context/workspace_context.py) en `kogniterm/core/context/workspace_context.py`, responsable de gestionar los directorios de trabajo, validar rutas y proporcionar una interfaz para el acceso al contexto. Utiliza `os` y `pathlib` de Python.
-   **Módulo de Análisis de Estructura de Carpetas**: Se implementó el módulo en [`kogniterm/core/context/folder_structure_analyzer.py`](kogniterm/core/context/folder_structure_analyzer.py), el cual analiza la estructura de carpetas y genera una representación jerárquica de archivos y directorios, aplicando patrones de ignorado.
-   **Módulo de Búsqueda de Archivos**: Se implementó el módulo en [`kogniterm/core/context/file_search_module.py`](kogniterm/core/context/file_search_module.py), que busca archivos específicos utilizando patrones de búsqueda y patrones de ignorado, empleando `os.walk`, `pathlib` y `fnmatch`.
-   **Módulo de Análisis de Archivos de Configuración**: Se implementó el módulo en [`kogniterm/core/context/config_file_analyzer.py`](kogniterm/core/context/config_file_analyzer.py), que analiza archivos `package.json`, `tsconfig.json` y `.eslintrc.js`, extrayendo información relevante. Se definieron `TypedDict` para un tipado estático adecuado.
-   **Módulo de Interacción con Git**: Se implementó el módulo en [`kogniterm/core/context/git_interaction_module.py`](kogniterm/core/context/git_interaction_module.py), que interactúa con el repositorio Git para obtener información sobre el estado del proyecto.
-   **Módulo de Gestión de Patrones de Ignorado**: Se implementó el módulo en [`kogniterm/core/context/ignore_pattern_manager.py`](kogniterm/core/context/ignore_pattern_manager.py), que analiza archivos `.gitignore` y proporciona patrones de ignorado. Se añadió la dependencia `gitignore-parser` a `kogniterm/requirements.txt`.
-   **Módulo de Observación del Sistema de Archivos (Opcional)**: Se implementó el módulo en [`kogniterm/core/context/file_system_watcher.py`](kogniterm/core/context/file_system_watcher.py), utilizando `watchdog` para detectar cambios en el sistema de archivos. Se actualizó `kogniterm/requirements.txt` y `setup.py` para incluir la dependencia `watchdog`. Se integró el `FileSystemWatcher` en `kogniterm/core/context/workspace_context.py`.
-   **Integración de Módulos para el Flujo de Trabajo de Inicialización**: Se implementó la función `initializeProjectContext` en [`kogniterm/core/context/project_context_initializer.py`](kogniterm/core/context/project_context_initializer.py), que orquesta la inicialización del contexto del proyecto, integrando todos los módulos mencionados.
---
## 20-09-2025 Corrección de TypeError por `await` en función síncrona

**Descripción general:** Se corrigió el error `TypeError: object bool can't be used in 'await' expression` que ocurría al procesar meta-comandos. El problema se debía a que se estaba usando la palabra clave `await` en una llamada a una función síncrona.

-   **Análisis de la función:** Se revisó la función `process_meta_command` en [`kogniterm/terminal/meta_command_processor.py`](kogniterm/terminal/meta_command_processor.py) y se confirmó que es una función síncrona (no `async def`).
-   **Eliminación de `await`:** Se modificó el archivo [`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py) en la línea 172 para eliminar la palabra clave `await` de la llamada a `self.meta_command_processor.process_meta_command(user_input)`, resolviendo así el `TypeError`.
---
## 20-09-2025 Corrección de Errores de Inicialización de Herramientas y Atributos

**Descripción general:** Se resolvieron dos errores críticos que impedían la correcta inicialización de KogniTerm: un `ValidationError` en `FileReadTool` debido a la falta de `workspace_context` y un `AttributeError` en `KogniTermApp` por intentar acceder a `interrupt_queue` antes de su inicialización.

-   **Corrección de `ValidationError` en `FileReadTool`:**
    -   **Problema:** La herramienta `FileReadTool`, al ser una clase Pydantic, requería `workspace_context` en su inicialización, pero la función `get_callable_tools` no lo estaba pasando correctamente.
    -   **Solución:** Se modificó [`kogniterm/core/tools/tool_manager.py`](kogniterm/core/tools/tool_manager.py) para incluir una lógica que detecta si una herramienta es una subclase de `BaseModel` (Pydantic) y si tiene un campo `workspace_context`. Si ambas condiciones se cumplen, se asegura que el `workspace_context` se pase como argumento durante la instanciación de la herramienta.
-   **Corrección de `AttributeError` en `KogniTermApp`:**
    -   **Problema:** El atributo `self.interrupt_queue` en `KogniTermApp` se estaba utilizando para inicializar `LLMService` antes de que `self.interrupt_queue` fuera realmente definido, lo que resultaba en un `AttributeError`.
    -   **Solución:** Se reordenaron las líneas de inicialización en el método `__init__` de [`kogniterm/terminal/kogniterm_app.py`](kogniterm/terminal/kogniterm_app.py) para asegurar que `self.interrupt_queue = queue.Queue()` se ejecute antes de la creación de la instancia de `LLMService`, resolviendo así el error.
---
## 20-09-2025 Implementación de Patrones de Ignorado Universales en IgnorePatternManager

**Descripción general:** Se modificó la clase `IgnorePatternManager` en [`kogniterm/core/context/ignore_pattern_manager.py`](kogniterm/core/context/ignore_pattern_manager.py) para incluir una lista de patrones de ignorado universales por defecto, además de los patrones leídos del archivo `.gitignore` del proyecto. Esto asegura que directorios comunes como `venv` y `.git` sean ignorados por defecto.

-   **Lista de Patrones Universales:** Se añadió `DEFAULT_IGNORE_PATTERNS` a la clase `IgnorePatternManager` con elementos como "venv/", ".git/", "__pycache__/", "*.pyc", "*.tmp", "*.log", ".env", ".DS_Store".
-   **Inicialización:** El constructor de `IgnorePatternManager` fue modificado para inicializar `self.universal_patterns` con `DEFAULT_IGNORE_PATTERNS`.
-   **Combinación de Patrones:** El método `get_ignore_patterns` ahora combina los `universal_patterns` con los patrones específicos del `.gitignore` del proyecto.
-   **Verificación de Ignorados:** El método `check_ignored` se actualizó para considerar ambos conjuntos de patrones (universales y de proyecto) al verificar si un archivo debe ser ignorado. Para ello, se crea un archivo temporal que contiene todos los patrones combinados, que luego es procesado por `gitignore_parser`.
---
## 20-09-2025 Implementación de la Lógica de Eventos del Sistema de Archivos en WorkspaceContext

**Descripción general:** Se implementó la lógica para manejar eventos del sistema de archivos en `WorkspaceContext` y se integró con `project_context_initializer.py`.

-   **Modificación de `WorkspaceContext`**: Se renombró el método `_handle_file_system_event` a `handle_file_system_event` en [`kogniterm/core/context/workspace_context.py`](kogniterm/core/context/workspace_context.py), se añadió una impresión para depuración `print(f"Evento del sistema de archivos detectado: {event} en {path})")` y se aseguró que se notifique a los suscriptores (`self._notify_callbacks()`).
-   **Integración con `project_context_initializer.py`**: El `FileSystemWatcher` en `WorkspaceContext` ahora utiliza el método público `handle_file_system_event` como su `callback`, lo que permite que los eventos del sistema de archivos sean manejados y notificados correctamente. Este cambio se gestiona internamente en `WorkspaceContext` y no requiere modificaciones directas en `project_context_initializer.py`.
---
## 20-09-2025 Eliminación de la Restricción de Lectura de Archivos en FileReadTool

**Descripción general:** Se eliminó la restricción que impedía a `FileReadTool` leer archivos fuera del espacio de trabajo. Esto permite una mayor flexibilidad al leer archivos del sistema.

-   **Modificación de `_run`:** Se eliminó la lógica condicional `if not self.workspace_context.isPathWithinWorkspace(path):` y el mensaje de error asociado en el método `_run` de [`kogniterm/core/tools/file_read_tool.py`](kogniterm/core/tools/file_read_tool.py:23).
-   **Actualización de la descripción:** Se actualizó la descripción de la herramienta en [`kogniterm/core/tools/file_read_tool.py`](kogniterm/core/tools/file_read_tool.py:12) para reflejar que ya no está restringida a archivos dentro del espacio de trabajo.
---
## 20-09-2025 Implementación de la Lógica de Eventos del Sistema de Archivos en WorkspaceContext y Robustez de Git
Descripcion general: Se implementó la lógica para actualizar el contexto del proyecto en el método `handle_file_system_event` de `kogniterm/core/context/workspace_context.py`, considerando diversos tipos de eventos del sistema de archivos. Además, se hizo el módulo de interacción con Git más robusto ante la ausencia de la librería `simple_git`.

-   **Implementación de `handle_file_system_event`**:
    -   Se agregó lógica para recargar archivos de configuración (`package.json`, `tsconfig.json`, `.eslintrc.js`/`.eslintrc.json`) usando `ConfigFileAnalyzer`.
    -   Se actualiza la estructura de carpetas (`FolderStructureAnalyzer`) en eventos de creación, eliminación o movimiento, y también en modificaciones de archivos no relacionados con configuraciones.
    -   Se actualiza el estado de Git (`GitInteractionModule`) ante cualquier cambio relevante en el workspace.
    -   Se gestionan los patrones de ignorado si el archivo `.gitignore` cambia, aprovechando la funcionalidad existente de `IgnorePatternManager`.
-   **Refactorización de `WorkspaceContext`**:
    -   Se eliminaron importaciones duplicadas y código anidado para limpiar el archivo `kogniterm/core/context/workspace_context.py`.
    -   Se añadió el atributo `_folder_structure` para almacenar la estructura de carpetas.
    -   Se añadió el método privado `_update_folder_structure` para encapsular la lógica de actualización de la estructura de carpetas.
    -   Se modificaron los métodos `addDirectory` y `removeDirectory` para que llamen a `_update_folder_structure` después de reiniciar el observador del sistema de archivos.
-   **Robustez de `GitInteractionModule`**:
    -   Se modificó `kogniterm/core/context/git_interaction_module.py` para incluir un bloque `try-except` al importar `simple_git`. Si la librería no está instalada, se utiliza un mock de `SimpleGit` que registra una advertencia y desactiva las funcionalidades de Git, permitiendo que el programa continúe ejecutándose sin errores fatales.
---
## 20-09-2025 Refactorización del Módulo de Interacción con Git

**Descripción general:** Se refactorizó el módulo de interacción con Git para reemplazar la librería `simple-git` (que no existe) por `GitPython`, una solución más robusta y estándar para interactuar con repositorios Git en Python.

- **Reemplazo de Librería:** Se actualizó `kogniterm/requirements.txt` para eliminar `simple-git` y añadir `GitPython`.
- **Actualización del Módulo:** Se reescribió `kogniterm/core/context/git_interaction_module.py` para usar `GitPython`. Se implementó una función `_get_repo` para manejar la inicialización del repositorio y se actualizaron las funciones `get_git_status` y `get_git_tracked_files` para usar la nueva librería, mejorando la robustez y el manejo de errores.
---
## 20-09-2025 Integración de GitInteractionModule en WorkspaceContext

**Descripción general:** Se integró `GitInteractionModule` en `WorkspaceContext` para gestionar de manera eficiente las interacciones con Git ante eventos del sistema de archivos, asegurando que solo se reaccione a cambios relevantes en archivos rastreados.

-   **Inicialización y Actualización de `GitInteractionModule`**:
    -   Se añadió un atributo `git_interaction_module` a la clase `WorkspaceContext`.
    -   Se inicializa `git_interaction_module` en el método `__post_init__` y se actualizan los archivos rastreados al inicio.
    -   Se asegura que `git_interaction_module` se reinicialice y actualice los archivos rastreados cuando se añaden o eliminan directorios (`addDirectory`, `removeDirectory`).
-   **Manejo de Eventos del Sistema de Archivos**:
    -   En `handle_file_system_event`, se verifica si el archivo modificado está rastreado por Git utilizando `git_interaction_module.is_tracked()`.
    -   Si el archivo está rastreado, se llama a `git_interaction_module.update_git_status()` para actualizar el estado de Git.
    -   Se elimina la llamada directa a `get_git_status` y se reemplaza por la interacción con la instancia de `GitInteractionModule`.
    ---
    ## 20-09-2025 Corrección de `ImportError` en `project_context_initializer.py`
    
    **Descripción general:** Se corrigió el `ImportError: cannot import name 'get_folder_structure' from 'kogniterm.core.context.folder_structure_analyzer'` en `kogniterm/core/context/project_context_initializer.py`. Este error se debía a que `get_folder_structure` fue refactorizada a un método de la clase `FolderStructureAnalyzer`.
    
    -   **Actualización de Importación:** Se modificó la importación en [`kogniterm/core/context/project_context_initializer.py`](kogniterm/core/context/project_context_initializer.py:5) para importar `FolderStructureAnalyzer` en lugar de la función `get_folder_structure`.
    -   **Instanciación y Uso:** Se ajustó la lógica en [`kogniterm/core/context/project_context_initializer.py`](kogniterm/core/context/project_context_initializer.py:38) para crear una instancia de `FolderStructureAnalyzer` y luego acceder a la estructura de carpetas a través del atributo `structure` de la instancia.
---
## 20-09-2025 Desactivación de Inicialización Automática de `project_context`

**Descripción general:** Se modificó la inicialización de `project_context` en el archivo `kogniterm/terminal/terminal.py` para evitar que se inicialice automáticamente al inicio, permitiendo que se establezca correctamente a través de un meta-comando.

-   **Modificación de `project_context`:** Se cambió la línea 146 en [`kogniterm/terminal/terminal.py`](kogniterm/terminal/terminal.py:146) de `project_context = await initializeProjectContext(os.getcwd())` a `project_context = None`. Esto asegura que el contexto del proyecto no se cargue automáticamente y espera la acción explícita del usuario a través de un meta-comando.
---
## 20-09-2025 Optimización del Rendimiento de FileCompleter

**Descripción general:** Se implementó un mecanismo de caché y un observador del sistema de archivos (`FileSystemWatcher`) en la clase `FileCompleter` para mejorar significativamente el rendimiento del autocompletado de archivos, evitando lecturas recursivas costosas en cada solicitud.

-   **Mecanismo de Caché en `FileCompleter`**:
    -   Se añadió `self._cached_files` y `self._cache_lock` a la clase `FileCompleter` en [`kogniterm/terminal/terminal.py`](kogniterm/terminal/terminal.py:86) para almacenar la lista de archivos y directorios.
    -   Se implementó `_load_files_into_cache()` para cargar los archivos una sola vez y `invalidate_cache()` para resetear la caché cuando sea necesario.
-   **Integración de `FileSystemWatcher`**:
    -   Se importó `FileSystemWatcher` y `threading` en [`kogniterm/terminal/terminal.py`](kogniterm/terminal/terminal.py).
    -   El constructor de `FileCompleter` ahora inicializa y arranca un `FileSystemWatcher` que observa el `workspace_directory`.
    -   El método `_on_file_system_event()` se encarga de invalidar la caché ante cualquier cambio detectado en el sistema de archivos.
-   **Actualización de `get_completions()`**:
    -   El método `get_completions()` en `FileCompleter` ahora utiliza `self._load_files_into_cache()` para obtener la lista de archivos, evitando así la llamada recursiva directa a la herramienta en cada invocación.
-   **Gestión del Ciclo de Vida del Observador**:
    -   Se añadió un método `dispose()` a `FileCompleter` para detener el `FileSystemWatcher` de forma segura cuando la aplicación finaliza.
    -   La función `_main_async()` en [`kogniterm/terminal/terminal.py`](kogniterm/terminal/terminal.py:142) se modificó para pasar el `workspace_directory` a `KogniTermApp` y para asegurar que `completer.dispose()` sea llamado en un bloque `finally` al salir de la aplicación.
---
## 20-09-2025 Asegurar el paso de `workspace_context` a las herramientas

**Descripción general:** Se aseguró que la instancia `workspace_context` se pase correctamente a las herramientas después de la inicialización del contexto, resolviendo el problema de que `LLMService` y sus herramientas no recibían la instancia actualizada de `WorkspaceContext`.

-   **Modificación de `kogniterm/terminal/terminal.py`:**
    -   Se modificó la función `_main_async` para inicializar `project_context` (que es el `WorkspaceContext`) antes de instanciar `LLMService`. Esto garantiza que `LLMService` se cree con el contexto de trabajo ya disponible.
-   **Modificación de `kogniterm/terminal/kogniterm_app.py`:**
    -   Se modificó el constructor de `KogniTermApp` para recibir la instancia de `LLMService` ya inicializada con el `workspace_context`.
    -   Se ajustó la inicialización de `FileOperationsTool` dentro de `KogniTermApp` para que reciba el `workspace_context` directamente de `self.project_context`.
---
## 20-09-2025 Desactivación de Inicialización Automática del Contexto del Proyecto

**Descripción general:** Se modificó la inicialización del contexto del proyecto en `kogniterm/terminal/terminal.py` para evitar su carga automática al inicio de KogniTerm. Esto asegura que la inicialización del contexto sea exclusivamente a través del meta-comando `%init_context`, corrigiendo errores de `Pylance` relacionados con la indefinición de `project_context`.

-   **Comentar inicialización automática:** Se comentó la línea que inicializaba automáticamente `project_context = await initializeProjectContext(workspace_directory)` en `kogniterm/terminal/terminal.py`.
-   **Inicialización condicional de `project_context`:** Se inicializó `project_context` a `None` y se modificó la instanciación de `LLMService` y `KogniTermApp` para que, si `project_context` es `None`, utilicen una instancia vacía de `WorkspaceContext`. Esto permite que la aplicación inicie sin errores antes de que el contexto del proyecto sea cargado explícitamente.
---
## 21-09-2025 Actualización del historial de conversación resumido
Descripción general: Se corrigió un problema donde el historial principal de la conversación (self.conversation_history) no se actualizaba con la versión resumida, a pesar de que el resumen se realizaba correctamente para la llamada actual al modelo de lenguaje.

- **Actualización de `self.conversation_history`**: Se modificó el método `invoke()` en [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py) para que, después de resumir el historial y crear `new_litellm_messages`, estos mensajes se conviertan de nuevo a objetos de LangChain y se asignen a `self.conversation_history`.
- **Guardado del historial actualizado**: Se añadió una llamada a `self._save_history(self.conversation_history)` inmediatamente después de actualizar `self.conversation_history` para asegurar que los cambios se persistan en el archivo de historial.
- **Función auxiliar `_from_litellm_message`**: Se creó una nueva función `_from_litellm_message` para facilitar la conversión de mensajes de LiteLLM a objetos de LangChain.
---
## 21-09-2025 Solución de errores de tipado y estabilidad en el resumen del historial
Descripción general: Se abordaron los errores de tipado en `kogniterm/terminal/kogniterm_app.py` y se mejoró la estabilidad del resumen del historial en `kogniterm/core/llm_service.py` al filtrar `ToolMessages` huérfanos.

- **Filtrado de `ToolMessages` huérfanos antes del resumen**: Se modificó la función `summarize_conversation_history()` en [`kogniterm/core/llm_service.py`](kogniterm/core/llm_service.py) para aplicar la lógica de filtrado de `ToolMessages` huérfanos a `self.conversation_history` antes de enviarlo a `litellm.completion`. Esto evita el `APIConnectionError` (`Missing corresponding tool call for tool response message`) que ocurría cuando el historial contenía un `ToolMessage` sin un `AIMessage` de invocación asociado.
- **Corrección de errores de tipado en `kogniterm/terminal/kogniterm_app.py`**: Se corrigieron los errores de Pylance relacionados con la asignación de `self.llm_service.conversation_history` a `self.agent_state.messages`. Se añadió `list()` al asignar `self.llm_service.conversation_history` para asegurar que se pase una copia explícita de la lista, resolviendo el problema de tipado.
---
## 21-09-2025 Corrección de `TypeError` en `initializeProjectContext()`
Descripción general: Se corrigió el `TypeError: initializeProjectContext() missing 1 required positional argument: 'directory'` que ocurría al iniciar la aplicación.

- **Paso del argumento `directory`**: Se modificó la llamada a `initializeProjectContext()` en [`kogniterm/terminal/terminal.py`](kogniterm/terminal/terminal.py) para pasar el argumento `directory=workspace_directory`, asegurando que la función reciba el parámetro requerido.
---
## 21-09-2025 Desactivación de Inicialización Automática del Contexto del Proyecto
Descripción general: Se deshabilitó la inicialización automática del contexto del proyecto al inicio de KogniTerm para permitir que la carga del contexto sea controlada por el usuario a través de un meta-comando.

- **Inicialización de `project_context` a `None`**: Se modificó la función `_main_async()` en [`kogniterm/terminal/terminal.py`](kogniterm/terminal/terminal.py) para inicializar `project_context = None` en lugar de llamar a `initializeProjectContext()` automáticamente.
- **Manejo de `project_context` nulo**: Se verificó que las instanciaciones de `LLMService` y `KogniTermApp` manejen correctamente el caso en que `project_context` sea `None`, utilizando una instancia de `WorkspaceContext()` vacía si es necesario.
---
## 21-09-2025 Forzar Desactivación de Inicialización Automática del Contexto del Proyecto
Descripción general: Se forzó la desactivación de la inicialización automática del contexto del proyecto sobrescribiendo el archivo `kogniterm/terminal/terminal.py`, ya que los intentos previos de `apply_diff` no persistieron.

- **Sobrescritura de `kogniterm/terminal/terminal.py`**: Se utilizó `write_to_file` para sobrescribir el archivo [`kogniterm/terminal/terminal.py`](kogniterm/terminal/terminal.py) asegurando que la línea de inicialización de `full_project_context` ahora sea `project_context = None`. Esto garantiza que el contexto del proyecto no se inicialice automáticamente al inicio de KogniTerm.
---
## 21-09-2025 Modificación de `FileUpdateTool` para confirmación obligatoria
Descripción general: Se modificó la herramienta `FileUpdateTool` para que siempre muestre el diff de los cambios propuestos y requiera una confirmación explícita antes de aplicarlos.

- **Eliminación del parámetro `confirm`**: Se eliminó el campo `confirm` de la clase `FileUpdateInput` y del método `_run` de `FileUpdateTool` en [`kogniterm/core/tools/file_update_tool.py`](kogniterm/core/tools/file_update_tool.py).
- **Generación de diff obligatoria**: La lógica de `_run` ahora siempre genera y devuelve el diff de los cambios si existen, indicando que se requiere confirmación. Si no hay cambios, devuelve un mensaje apropiado. La aplicación del cambio real en el archivo ahora se espera que sea manejada por el agente después de recibir una confirmación explícita del usuario (fuera de la herramienta).