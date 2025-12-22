# Registro de Cambios de KogniTerm

## 19-11-2025 Eliminación de logs de depuración y mejora de la visibilidad de acciones de herramientas

Se han eliminado o comentado varios mensajes de depuración (DEBUG) en los archivos `kogniterm/core/llm_service.py` y `kogniterm/core/tools/advanced_file_editor_tool.py` para limpiar la salida de la consola. Además, se han añadido mensajes informativos en `AdvancedFileEditorTool` para que la herramienta muestre de manera más clara las acciones que está realizando.

- **Punto 1**: Se comentaron todas las líneas `print` que generaban mensajes de depuración relacionados con el historial en `kogniterm/core/llm_service.py`.
- **Punto 2**: Se comentaron todas las líneas `print` que generaban mensajes de depuración relacionados con la configuración de la API y el rate limiting en `kogniterm/core/llm_service.py`.
- **Punto 3**: Se comentó la línea `logger.debug` que mostraba los mensajes finales enviados a LiteLLM en `kogniterm/core/llm_service.py`.
- **Punto 4**: Se comentaron todas las líneas `print` que generaban mensajes de depuración relacionados con la interrupción de la ejecución de herramientas en `kogniterm/core/llm_service.py`.
- **Punto 5**: Se comentaron todas las líneas `print` que generaban mensajes de depuración en `kogniterm/core/tools/advanced_file_editor_tool.py`.
- **Punto 6**: Se añadió un mensaje informativo al inicio del método `_run` de `AdvancedFileEditorTool` para indicar la invocación de la herramienta.
- **Punto 7**: Se añadieron mensajes informativos específicos para cada acción (`insert_line`, `replace_regex`, `prepend_content`, `append_content`) en `AdvancedFileEditorTool` para describir la operación que se va a realizar.
- **Punto 8**: Se añadió un mensaje informativo cuando la actualización se aplica en `AdvancedFileEditorTool`.
- **Punto 9**: Se añadió un mensaje informativo cuando no se requieren cambios en `AdvancedFileEditorTool`.

---

## 19-11-2025 Solución de Pérdida de Contexto con Salidas Largas y Duplicación de Mensajes

Se solucionó un problema crítico donde el agente perdía el contexto de la conversación al procesar salidas de comandos extensas (como `docker ps -a`). Esto se debía a una combinación de falta de truncamiento en el flujo manual, duplicación de mensajes en el historial y falta de persistencia inmediata.

- **Punto 1**: Implementación de truncamiento inteligente en `bash_agent.py` (10k caracteres, preservando inicio y fin).
- **Punto 2**: Implementación de truncamiento idéntico en `CommandApprovalHandler.py` para el flujo de confirmación manual.
- **Punto 3**: Eliminación de duplicación de `ToolMessage` en `kogniterm_app.py` para evitar mensajes redundantes.
- **Punto 4**: Agregado de guardado explícito del historial (`_save_history`) en `bash_agent.py` después de ejecutar herramientas para asegurar persistencia.
- **Punto 5**: Ajuste de límites mínimos en `history_manager.py` (30 mensajes, 50k caracteres) para garantizar espacio para el contexto.
- **Punto 6**: Mejora de logs y truncamiento bidireccional en `llm_service.py` para mejor visibilidad y manejo de mensajes largos.

---

## 19-11-2025 Corrección de Problemas Visuales en KogniTerm

Se han resuelto varios problemas visuales y de renderizado en la terminal.

- **Punto 1**: Corrección del renderizado de párrafos en las confirmaciones de comandos.
- **Punto 2**: Implementación de resaltado de sintaxis para Diffs en `CommandApprovalHandler` utilizando `rich.syntax.Syntax` en lugar de texto plano.
- **Punto 3**: Eliminación de la duplicación de salida en `CommandExecutor` removiendo un `yield` redundante en el bloque `finally`.
- **Punto 4**: Corrección de la animación del Spinner en `AgentInteractionManager` instanciando el objeto `Spinner` una sola vez para evitar el parpadeo y reinicio constante.

---

## 19-11-2025 Corrección de `SyntaxError` en `kogniterm/core/history_manager.py`

Se ha corregido un `SyntaxError: unterminated triple-quoted string literal` en el archivo `kogniterm/core/history_manager.py`. El error se debía a un docstring de varias líneas que no estaba correctamente cerrado.

- **Punto 1**: Se identificó y eliminó un cierre de docstring (`"""`) incorrectamente añadido al final del archivo, que estaba causando el `SyntaxError`.
- **Punto 2**: Se verificó la corrección del error ejecutando `python3 -m py_compile kogniterm/core/history_manager.py`, el cual se ejecutó sin problemas.

---

## 19-11-2025 Corrección de `AttributeError` en `kogniterm/core/llm_service.py` y Prevención de Sobrescritura de Historial

Se ha corregido un `AttributeError` crítico y se ha implementado una protección para evitar que el historial de conversación sea sobrescrito por procesos auxiliares.

- **Punto 1**: Se corrigió `AttributeError: 'LLMService' object has no attribute '_summarize_conversation_history'` cambiando la llamada a `self.summarize_conversation_history` en `LLMService.invoke`.
- **Punto 2**: Se agregó el parámetro `save_history` (por defecto `True`) a `LLMService.invoke` y `HistoryManager.get_processed_history_for_llm`.
- **Punto 3**: Se modificó `CommandApprovalHandler` para llamar a `invoke` con `save_history=False` al generar explicaciones de comandos, evitando así que estos prompts temporales sobrescriban el historial principal de la conversación.

---

## 20-11-2025 Corrección de `AttributeError` en `kogniterm/core/llm_service.py`

Se ha corregido un `AttributeError: 'LLMService' object has no attribute 'settings'` en el archivo `kogniterm/core/llm_service.py`. El error se debía a un acceso incorrecto a los atributos de configuración.

- **Punto 1**: Se modificaron las líneas 377 y 378 en `kogniterm/core/llm_service.py` para usar `self.max_conversation_tokens` en lugar de `self.settings.max_conversation_tokens`, ya que `max_conversation_tokens` es un atributo directo de la instancia `LLMService`.

---

## 20-11-2025 Corrección de `TypeError: object of type 'NoneType' has no len()` en `kogniterm/core/history_manager.py`

Se ha corregido un error donde `_truncate_history` devolvía `None` si no se realizaba ningún truncamiento, causando un fallo en `llm_service.py`.

- **Punto 1**: Se modificó `_truncate_history` en `kogniterm/core/history_manager.py` para asegurar que siempre devuelva una lista de mensajes, incluso cuando no se entra en el bucle de truncamiento.

---

## 20-11-2025 Corrección de Bug en Listas JSON y Ocultamiento de Salida de Herramientas

Se han realizado dos correcciones importantes en `kogniterm/core/agents/bash_agent.py`: una para solucionar un bug en el procesamiento de listas JSON y otra para mejorar la experiencia de usuario ocultando la salida cruda de herramientas no interactivas.

- **Punto 1**: Se corrigió un error en `execute_single_tool` que filtraba incorrectamente los elementos de listas JSON que no cumplían con un esquema específico (content/file_path), causando que herramientas como `brave_search` devolvieran listas vacías. Ahora se preservan todos los elementos.
- **Punto 2**: Se modificó `execute_single_tool` para que solo se muestre la salida en tiempo real (streaming) de la herramienta `execute_command`. La salida de otras herramientas se oculta al usuario para reducir el ruido visual, mostrando solo la acción y el resultado final procesado por el agente.

---

## 20-11-2025 Corrección de Parpadeo del Spinner de Carga

Se ha solucionado el problema del parpadeo constante del spinner de carga del agente.

- **Punto 1**: Se eliminó la implementación del spinner en un hilo separado en `kogniterm/terminal/agent_interaction_manager.py`, que entraba en conflicto con la actualización de la interfaz en `bash_agent.py`.
- **Punto 2**: Se integró el spinner directamente en `kogniterm/core/agents/bash_agent.py` utilizando `rich.Live`. Ahora el spinner se muestra inicialmente y es reemplazado suavemente por el texto de la respuesta del agente a medida que se recibe, eliminando el conflicto de renderizado y el parpadeo.

---

## 20-11-2025 Aumento del Límite de Recursión y Eliminación de Spinner

Se ha aumentado el límite de recursión para la ejecución del agente y se ha simplificado la interfaz eliminando el spinner de carga.

- **Punto 1**: Se aumentó el `recursion_limit` a 100 en la invocación del grafo del agente en `kogniterm/terminal/agent_interaction_manager.py` para prevenir el error "Recursion limit of 25 reached".

---

## 23-11-2025 Implementación del Sistema RAG de Codebase

Se ha implementado el sistema RAG (Retrieval-Augmented Generation) para permitir al agente indexar y buscar en el código base del proyecto.

- **Punto 1**: Creación de `kogniterm/terminal/config_manager.py` para gestionar configuraciones globales y por proyecto.
- **Punto 2**: Implementación de comandos CLI `config` para establecer y obtener configuraciones.
- **Punto 3**: Creación de `kogniterm/core/embeddings_service.py` con soporte para proveedores Gemini y OpenAI.
- **Punto 4**: Desarrollo de `kogniterm/core/context/codebase_indexer.py` para dividir archivos de código en chunks y generar embeddings.
- **Punto 5**: Implementación de `kogniterm/core/context/vector_db_manager.py` utilizando ChromaDB para almacenamiento persistente de vectores.
- **Punto 6**: Creación de la herramienta `CodebaseSearchTool` en `kogniterm/core/tools/codebase_search_tool.py` para permitir al agente buscar en el código.
- **Punto 7**: Integración del comando CLI `kogniterm index refresh` en `terminal.py` para indexar el proyecto manualmente.
- **Punto 8**: Registro de `CodebaseSearchTool` en `kogniterm/terminal/kogniterm_app.py` para que esté disponible para el agente.
- **Punto 9**: Adición de `chromadb` a `requirements.txt`.
- **Punto 10**: Implementación de soporte para **Ollama** como proveedor de embeddings en `EmbeddingsService`.
- **Punto 11**: Se fijó la versión de `urllib3<2` en `requirements.txt` para evitar conflictos de dependencia con `requests` que causaban un `ImportError`.
- **Punto 12**: Se actualizó `pyproject.toml` para incluir todas las dependencias faltantes (incluyendo `chromadb`, `urllib3<2`, `google-generativeai`, etc.) asegurando que `pipx` las instale correctamente.

---

## 24-11-2025 Corrección de `CodebaseSearchTool` y Prompt de Indexación al Inicio

Se ha corregido un error de ejecución asíncrona en `CodebaseSearchTool` y se ha mejorado la experiencia de usuario al iniciar KogniTerm.

- **Punto 1**: Se implementó el método síncrono `_run` en `kogniterm/core/tools/codebase_search_tool.py` y se actualizó `_arun` para envolverlo en un hilo, solucionando el error `CodebaseSearchTool is an async tool, use _arun instead`.
- **Punto 2**: Se modificó `kogniterm/terminal/kogniterm_app.py` para preguntar al usuario al inicio si desea indexar el contenido del directorio actual.
- **Punto 3**: Se integró el proceso de indexación con una barra de progreso visual en el inicio de la aplicación si el usuario confirma la acción.

---

## 24-11-2025 Indexación de Codebase en Segundo Plano

Se ha optimizado el proceso de indexación inicial del codebase para que se ejecute en segundo plano, permitiendo al usuario utilizar la aplicación inmediatamente sin bloqueos.

- **Punto 1**: Se modificó `CodebaseIndexer.index_project` en `kogniterm/core/context/codebase_indexer.py` para aceptar un parámetro `show_progress`, permitiendo la ejecución silenciosa sin barra de progreso visual.
- **Punto 2**: Se actualizó `KogniTermApp` en `kogniterm/terminal/kogniterm_app.py` para ejecutar la indexación como una tarea asíncrona en segundo plano (`asyncio.create_task`) tras la confirmación del usuario.
- **Punto 3**: Se implementó la ejecución de operaciones pesadas de base de datos vectorial (`vector_db.add_chunks`) en un hilo separado (`asyncio.to_thread`) para evitar bloquear el bucle de eventos principal durante la indexación en segundo plano.

---

## 24-11-2025 Corrección de CodebaseSearchTool y Mejoras de UI en Indexación

Se han realizado correcciones y mejoras en la experiencia de indexación y búsqueda de código.

- **Punto 1**: Se eliminó el método `_arun` de `CodebaseSearchTool` en `kogniterm/core/tools/codebase_search_tool.py` para definirla explícitamente como una herramienta síncrona, resolviendo el error "CodebaseSearchTool is an async tool, use _arun instead".
- **Punto 2**: Se implementó una barra de progreso en la parte inferior de la terminal (`bottom_toolbar`) en `KogniTermApp` para mostrar el estado de la indexación en segundo plano sin interferir con el prompt del usuario.
- **Punto 3**: Se añadió una verificación al inicio (`VectorDBManager.is_indexed`) para detectar si el proyecto ya está indexado y preguntar al usuario si desea "RE-INDEXAR" en lugar de indexar desde cero.

---

## 24-11-2025 Implementación de Ideas "Kilo Code" (Fase 1)

Se han incorporado mejoras significativas en la indexación y búsqueda semántica, inspiradas en Kilo Code.

- **Punto 1**: Se enriqueció `CodebaseIndexer` para inferir y almacenar el lenguaje de programación (`language`) y el tipo de bloque (`type`) en los metadatos de cada chunk.
- **Punto 2**: Se actualizó `VectorDBManager.search` para soportar filtros opcionales por ruta de archivo (`file_path_filter`) y lenguaje (`language_filter`).
- **Punto 3**: Se modificó `CodebaseSearchTool` para exponer estos nuevos filtros como argumentos, permitiendo al agente realizar búsquedas más precisas (ej: "buscar función X en archivos python").
- **Corrección**: Se solucionó un error `NameError: name 'HTML' is not defined` en `KogniTermApp` importando la clase necesaria.

---

## 24-11-2025 Soporte para .gitignore y .kognitermignore

Se ha mejorado el mecanismo de indexación para respetar los archivos de ignorado estándar.

- **Punto 1**: `CodebaseIndexer` ahora lee automáticamente los patrones de `.gitignore` y `.kognitermignore` en la raíz del proyecto.
- **Punto 2**: Los archivos y directorios que coincidan con estos patrones (como `venv`, `.git`, `__pycache__`) serán ignorados durante la indexación, mejorando la eficiencia y relevancia de la búsqueda.
- **Corrección**: Se implementó un filtrado en `CodebaseIndexer` para descartar chunks que no hayan generado embeddings válidos, evitando errores de "empty embedding" en ChromaDB.
- **Corrección**: Se actualizó `VectorDBManager.add_chunks` para guardar correctamente los metadatos `language` y `type`, permitiendo que los filtros de búsqueda funcionen correctamente.

---

## 26-11-2025 Corrección de NameError: name 'Optional' is not defined en CodebaseSearchTool

Se ha corregido un `NameError` en `kogniterm/core/tools/codebase_search_tool.py` que ocurría porque `Optional` no estaba importado explícitamente desde el módulo `typing`.

- **Punto 1**: Se añadió `from typing import Optional` a las importaciones en `kogniterm/core/tools/codebase_search_tool.py` para asegurar que `Optional` esté definido y disponible para su uso en las anotaciones de tipo de Pydantic.

---

## 26-11-2025 Corrección de Unexpected Indent en CodebaseIndexer

Se ha corregido un `unexpected indent` en `kogniterm/core/context/codebase_indexer.py` en la línea 199. El error se debía a una indentación incorrecta de un bloque de código dentro de la función `index_project`.

- **Punto 1**: Se ajustó la indentación del bloque de código que maneja la generación de embeddings dentro del `if show_progress:` para que estuviera al nivel correcto, resolviendo el `SyntaxError`.

---

## 26-11-2025 Actualización de README y eliminación de referencias al orquestador

Se actualizó el archivo README.md para eliminar referencias obsoletas al "orquestador" y al comando mágico `%agentmode`, reflejando que ahora se utiliza un único agente inteligente.

- **Punto 1**: Se eliminó la mención a `%agentmode` en la lista de comandos mágicos en `README.md`.
- **Punto 2**: Se actualizó la descripción de "Agentes Inteligentes" a "Agente Inteligente" en `README.md`, eliminando la distinción entre modos `bash` y `orchestrator`.

---

## 28-11-2025 Corrección de Duplicación en Explicación de Comandos

Se ha corregido un problema donde la explicación de los comandos aparecía duplicada (una vez en el panel de UI y otra en el texto del agente). También se eliminó código duplicado en `terminal_ui.py`.

- **Punto 1**: Se eliminó la definición duplicada de la clase `CommandApprovalHandler` al final del archivo `kogniterm/terminal/terminal_ui.py`. Esta clase ya estaba correctamente definida en `kogniterm/terminal/command_approval_handler.py`.
- **Punto 2**: Se actualizó el prompt del sistema del agente en `kogniterm/core/agents/bash_agent.py` para instruir explícitamente al agente que NO explique los comandos en su respuesta de texto, ya que la interfaz de usuario ya proporciona una explicación visual en el panel de confirmación.

---

## 28-11-2025 Refuerzo de Prompt para Evitar Duplicidad de Explicaciones

Se ha refuerzo la instrucción en el prompt del sistema para evitar que el agente explique los comandos de terminal en su respuesta de texto, eliminando así la duplicidad con el panel de confirmación.

- **Punto 1**: Se modificó la instrucción en `kogniterm/core/agents/bash_agent.py` para ser mucho más estricta y explícita ("NO expliques comandos de terminal... Esto es CRÍTICO"), indicando al agente que solo mencione la acción general y deje la explicación técnica al sistema automático.

- **Punto 2**: Se corrigió un error lógico en `CommandApprovalHandler.py` que causaba la duplicación exacta del texto de la explicación. El problema era que el bucle acumulaba tanto los fragmentos de texto transmitidos (streaming) como el mensaje final completo (`AIMessage`) que `llm_service` emite al final. Se añadió una condición para ignorar el contenido del `AIMessage` final si ya se había acumulado texto mediante streaming.

---

## 30-11-2025 Mejora en el Manejo de Confirmaciones de Herramientas para Modelos No Gemini

Se han implementado mejoras en la lógica de `LLMService` para que los modelos no Gemini manejen de manera más robusta las confirmaciones de herramientas, evitando bucles y esperas innecesarias.

- **Punto 1**: Se reforzó la `tool_confirmation_instruction` en el mensaje de sistema global de `LLMService` para ser más explícita y enfática sobre la necesidad de esperar la confirmación del usuario antes de generar nuevas acciones o texto.
- **Punto 2**: Se añadió un mensaje de sistema de "bloqueo" dinámico en `LLMService.invoke`. Este mensaje se inyecta en el prompt del LLM cuando se detecta que hay una confirmación de herramienta pendiente (`status: "requires_confirmation"` en el último `ToolMessage`), instruyendo al modelo a pausar su generación y esperar la respuesta del usuario.

---

## 30-11-2025 Añadido de Logging de Depuración para LiteLLM

Se ha añadido un log de depuración en `kogniterm/core/llm_service.py` para capturar los `delta` recibidos de LiteLLM durante la generación de respuestas. Esto ayudará a diagnosticar errores relacionados con el formato de las respuestas del modelo, especialmente en llamadas a herramientas.

- **Punto 1**: Se añadió la línea `logger.debug(f"DEBUG: LiteLLM Delta recibido: {delta}")` dentro del bucle de procesamiento de chunks en el método `invoke` de `LLMService` en `kogniterm/core/llm_service.py`.

---

## 20-12-2025 Implementación de Cambio de Temas

Se ha implementado la funcionalidad para cambiar el tema de colores de la interfaz de KogniTerm en tiempo de ejecución.

- **Punto 1**: Se refactorizó `ColorPalette` en `kogniterm/terminal/themes.py` para soportar múltiples temas y la carga dinámica de colores. Se añadieron los temas: 'default', 'ocean', 'matrix' y 'sunset'.
- **Punto 2**: Se añadió el meta-comando `%theme` (o `%tema`) en `kogniterm/terminal/meta_command_processor.py` para permitir al usuario cambiar el tema desde la terminal (ej: `%theme ocean`).

---

## 20-12-2025 Solución al Límite de Tamaño de Lote en ChromaDB

Se ha corregido un error que impedía la indexación de proyectos grandes debido a que el número de fragmentos (chunks) superaba el límite máximo permitido por ChromaDB en una sola operación (5461).

- **Punto 1**: Se implementó una lógica de procesamiento por lotes (batching) en el método `add_chunks` de `kogniterm/core/context/vector_db_manager.py`.
- **Punto 2**: El tamaño del lote se fijó en 5000 fragmentos, lo cual es seguro y cumple con las restricciones de la API de ChromaDB.
- **Punto 3**: Se añadió logging informativo para mostrar el progreso de cada lote durante la indexación, facilitando el seguimiento en proyectos extensos.
- **Punto 4**: Esta mejora protege tanto la indexación manual (`kogniterm index refresh`) como la indexación automática en segundo plano al iniciar la aplicación.

---

## 20-12-2025 Solución de Errores de Instanciación en Herramientas (CodebaseSearchTool y SearchMemoryTool)

Se han corregido errores críticos que impedían la correcta instanciación de las herramientas `CodebaseSearchTool` y `SearchMemoryTool` debido a la falta de argumentos obligatorios y dependencias no inicializadas.

- **Punto 1**: Se modificó `LLMService` en `kogniterm/core/llm_service.py` para inicializar `EmbeddingsService` y `VectorDBManager` en su constructor y pasarlos al `ToolManager`.
- **Punto 2**: Se actualizó `ToolManager` en `kogniterm/core/tools/tool_manager.py` para aceptar `embeddings_service` y `vector_db_manager` en su `__init__` y distribuirlos a las herramientas que los requieran.
- **Punto 3**: Se mejoró la robustez de `ToolManager.load_tools` para detectar dependencias tanto en la firma del `__init__` como en los campos del modelo Pydantic (`model_fields`).
- **Punto 4**: Se implementó el método `set_agent_state` en `ToolManager` para permitir la vinculación tardía del estado del agente a las herramientas.
- **Punto 5**: Se modificó `kogniterm/terminal/terminal.py` para vincular el `AgentState` con el `ToolManager` inmediatamente después de su creación.
- **Punto 6**: Se actualizaron `CodebaseSearchTool` y `SearchMemoryTool` para hacer que sus dependencias (`vector_db_manager`, `embeddings_service`, `agent_state`) sean opcionales en la instanciación, evitando errores de validación de Pydantic, y se añadieron comprobaciones de seguridad antes de su uso.
- **Punto 7**: Se corrigió un `AttributeError: 'NoneType' object has no attribute 'schema'` en `LLMService.__init__` al generar `tool_schemas`, añadiendo validaciones para herramientas sin esquema de argumentos o que usan Pydantic v2.
- **Punto 8**: Se eliminó el bloque de inicialización manual de herramientas RAG en `KogniTermApp` (`kogniterm/terminal/kogniterm_app.py`), evitando el error de duplicación de funciones (`Duplicate function declaration found: codebase_search`) al estar ya gestionado por `LLMService`.
- **Punto 9**: Se corrigió un `TypeError` en el constructor de `AgentState` al recibir el argumento inesperado `history_for_api`. Se reintegró este campo como opcional en la `dataclass` y se añadió lógica en `__post_init__` para mantener la compatibilidad con versiones anteriores del código.
- **Punto 10**: Se aumentó la verbosidad del `ResearcherAgent` (`kogniterm/core/agents/researcher_agent.py`). Ahora el agente muestra paneles detallados con las herramientas ejecutadas, sus argumentos y los resultados obtenidos, mejorando la transparencia del proceso de investigación. Se corrigió un error de importación (`NameError: Console`) introducido durante esta mejora.
- **Punto 11**: Se corrigió la visualización de la salida de herramientas en `ResearcherAgent` para manejar correctamente los generadores. Además, se implementó un sistema de **Rate Limiting** en `LLMService` limitado a 5 llamadas por minuto para evitar bloqueos por parte de las APIs de los modelos.
- **Punto 12**: Se habilitó el paralelismo de herramientas en `LLMService` aumentando `max_workers` a 10 y eliminando la restricción de ejecución única. Esto permite que agentes (que actúan como herramientas) puedan invocar otras herramientas de forma anidada sin conflictos de bloqueo.
- **Punto 13**: Se eliminó la herramienta `ResearchTool` (`kogniterm/core/tools/research_tool.py`) por ser redundante con `CallAgentTool`. Ahora el orquestador utiliza `CallAgentTool` para invocar tanto al `CodeAgent` como al `ResearcherAgent`, simplificando el conjunto de herramientas disponibles para el modelo.

---

## 20-12-25 Unificación del Sistema de Ignorado (venv, node_modules y .gitignore)

Se ha implementado un sistema robusto y unificado para ignorar archivos y carpetas irrelevantes en toda la aplicación, respetando fielmente el archivo `.gitignore` del usuario.

- **Punto 1**: Se mejoró la lógica de comparación de patrones en `kogniterm/core/context/codebase_indexer.py` para manejar correctamente rutas relativas y nombres base, asegurando que `node_modules` y otros patrones complejos se ignoren durante el indexado.
- **Punto 2**: Se actualizó `kogniterm/core/context/workspace_context.py` para cargar y respetar el `.gitignore` al inicio, proporcionando al agente una visión limpia del proyecto.
- **Punto 3**: Se modificó `kogniterm/core/tools/file_operations_tool.py` para que el listado recursivo de directorios filtre automáticamente los elementos según las reglas del `.gitignore`.
- **Punto 4**: Se añadieron directorios comunes (`dist`, `build`, `target`, `venv`, `.venv`) a las listas de exclusión por defecto como medida de seguridad adicional.

---

## 20-12-25 Limpieza de Logs de Depuración al Inicio

Se han silenciado los mensajes de depuración (`DEBUG: ...`) que aparecían durante la inicialización de la aplicación para mejorar la experiencia de usuario y proporcionar un inicio más limpio.

- **Punto 1**: Se comentaron los mensajes `print` de depuración en `kogniterm/core/llm_service.py` relacionados con la inicialización de servicios, herramientas y tokenizer.
- **Punto 2**: Se comentaron los mensajes `print` de depuración en `kogniterm/core/context/vector_db_manager.py` relacionados con la conexión y configuración de ChromaDB.

---

## 20-12-25 Mejora en el Manejo de Errores de API (LiteLLM/OpenRouter) e Inyección de Fallbacks

Se ha implementado un manejo de excepciones más robusto para las llamadas al modelo y se han optimizado las definiciones de herramientas para mejorar la compatibilidad con proveedores de OpenRouter.

- **Punto 1**: Se mejoró el bloque `try-except` en `LLMService.invoke` para capturar errores de LiteLLM y proveedores externos (como OpenRouter), proporcionando mensajes amigables al usuario.
- **Punto 2**: Se optimizó la conversión de herramientas en `LLMService` para eliminar metadatos de Pydantic (como títulos) que causaban problemas con ciertos proveedores de OpenRouter (OpenInference).
- **Punto 3**: Se implementó una protección en `LLMService.invoke` para detectar respuestas vacías del modelo. Si el modelo no devuelve texto ni llamadas a herramientas, se inyecta un mensaje de aviso automático para evitar que el flujo del agente falle.
- **Punto 4**: Se eliminó la impresión de tracebacks técnicos en la terminal principal, moviéndolos a logs de depuración internos para mantener la interfaz limpia.
- **Punto 5**: Se configuró `litellm.drop_params = True` y se añadieron cabeceras específicas de OpenRouter (`HTTP-Referer`, `X-Title`) para maximizar la compatibilidad con todos los modelos y proveedores de OpenRouter, evitando errores de tipo `BadRequest`.
- **Punto 6**: Se corrigió un error de `BadRequest` en proveedores estrictos como Mistral mediante la implementación de un generador de IDs de herramientas corto (9 caracteres alfanuméricos), reemplazando los UUIDs largos que eran rechazados por la API.
- **Punto 7**: Se corrigió un `NameError: name 'traceback' is not defined` en `LLMService.invoke` añadiendo la importación faltante del módulo `traceback`.
- **Punto 8**: Se reforzó la lógica de envío de IDs de herramientas para asegurar que incluso los IDs provenientes del historial sean truncados a 9 caracteres si exceden ese límite, garantizando compatibilidad continua con Mistral.
- **Punto 9**: Se implementó una limpieza profunda de esquemas de herramientas (eliminando `additionalProperties`, `definitions`, `default`) y se optimizó el envío del parámetro `tools` para maximizar la compatibilidad con proveedores estrictos de OpenRouter.
- **Punto 10**: Se reforzó la prevención de mensajes vacíos inyectando contenido descriptivo automático tanto en respuestas de texto como en llamadas a herramientas sin contenido textual previo.
- **Punto 11**: Se eliminó la duplicación de mensajes de usuario (triplicación) mediante la eliminación de appends redundantes en `AgentInteractionManager` y `KogniTermApp`, y se implementó una deduplicación por contenido en `LLMService.invoke`.
- **Punto 12**: Se unificaron los mensajes de sistema consecutivos en un solo bloque para mejorar la compatibilidad con Mistral y otros modelos estrictos.
- **Punto 13**: Se corrigió un `TypeError: 'NoneType' object does not support item assignment` en `HistoryManager._save_history` asegurando que `self.conversation_history` se inicialice correctamente como una lista antes de realizar una actualización in-place.

---

## 21-12-2025 Eliminación de Herramientas de Archivo Redundantes

Se eliminaron las herramientas file_read_recursive_directory_tool, file_read_tool, file_delete_tool y file_create_tool por ser redundantes con otras herramientas existentes como file_operations_tool y advanced_file_editor_tool. Se limpiaron las importaciones y registros en tool_manager.py y terminal.py para mantener la consistencia del código.

- **Eliminación de archivos**: Se eliminaron los archivos kogniterm/core/tools/file_read_recursive_directory_tool.py, kogniterm/core/tools/file_read_tool.py, kogniterm/core/tools/file_delete_tool.py y kogniterm/core/tools/file_create_tool.py.
- **Limpieza de importaciones en tool_manager.py**: Se removieron las importaciones de las clases eliminadas y se eliminaron de la lista ALL_TOOLS_CLASSES.
- **Modificación de FileCompleter en terminal.py**: Se eliminó la dependencia de file_read_recursive_directory_tool, modificando el método _load_files_into_cache para no cargar archivos, y se actualizaron las importaciones.
- **Actualización de referencias**: Se verificaron y limpiaron todas las referencias a estas herramientas en el código base.

---

## 21-12-2025 Implementación de Herramienta de Análisis de Código (CodeAnalysisTool)

Se ha implementado una nueva herramienta, `CodeAnalysisTool`, que permite realizar análisis estático de código Python utilizando la librería `radon`. Esta herramienta proporciona métricas de complejidad ciclomática, índice de mantenibilidad y métricas raw (líneas de código, comentarios, etc.).

- **Punto 1**: Se añadió `radon` a las dependencias en `pyproject.toml`.
- **Punto 2**: Se creó el archivo `kogniterm/core/tools/code_analysis_tool.py` con la implementación de la herramienta.
- **Punto 3**: Se registró `CodeAnalysisTool` en `kogniterm/core/tools/tool_manager.py` para que esté disponible para el agente.
- **Punto 4**: Se realizaron ajustes en `kogniterm/core/llm_service.py` para resolver errores de Pylance relacionados con la gestión de `tool_calls` y la redefinición de métodos, asegurando la correcta integración de la nueva herramienta.

---

## 21-12-25 Implementación Completa y Corrección de Errores en CodeAgent

Se completó la implementación del `CodeAgent` en `kogniterm/core/agents/code_agent.py`, asegurando la funcionalidad de streaming y resolviendo varios errores de Pylance relacionados con la tipificación y el manejo del historial.

- **Adaptación de `handle_tool_confirmation`**: Se adaptó la función `handle_tool_confirmation` para el `CodeAgent`, alineándola con la lógica robusta de confirmación y re-ejecución de herramientas del `BashAgent`.
- **Corrección de Pylance en `AgentState`**: Se modificó `kogniterm/core/agent_state.py` para cambiar el tipo de `file_update_diff_pending_confirmation` a `Optional[Union[str, Dict[str, Any]]]` y se ajustaron las llamadas a `load_history` y `save_history` para que recibieran una instancia de `LLMService`.
- **Corrección de Pylance en `CodeAgent`**: Se resolvieron los errores de Pylance en `kogniterm/core/agents/code_agent.py` relacionados con el manejo de `tool_args` como `Optional[Dict[str, Any]]` y se aseguró el uso correcto de `state.save_history(llm_service)`.
- **Actualización de `call_model_node`**: Se revisó `call_model_node` para asegurar que el streaming y la interacción con `llm_service.invoke` fueran correctos, incluyendo el manejo de `AIMessage` y el guardado del historial.
- **Actualización de `execute_single_tool` y `execute_tool_node`**: Se corrigió la llamada a `execute_single_tool` en `execute_tool_node` para incluir el parámetro `terminal_ui` y se mejoró el manejo de excepciones (`UserConfirmationRequired`, `InterruptedError`).
- **Ajuste de `should_continue`**: Se ajustó la lógica de `should_continue` para considerar `state.command_to_confirm` y `state.file_update_diff_pending_confirmation`.
- **Imports y Grafo**: Se verificaron y añadieron los imports necesarios, y se confirmó que la construcción del grafo en `create_code_agent` era correcta.

---

## 21-12-2025 Eliminación de Truncamiento de Salida en `file_operations_tool.py`

Se eliminó la limitación de truncamiento de la salida en la función `_read_file` del archivo `kogniterm/core/tools/file_operations_tool.py`, lo que permite que el contenido completo de los archivos leídos sea enviado al LLM.

- **Punto 1**: Se eliminó la línea de código que truncaba el contenido del archivo a un número máximo de caracteres en la función `_read_file`.
- **Punto 2**: Se eliminó la constante `MAX_FILE_CONTENT_LENGTH` que definía el límite de truncamiento, ya que no es necesaria.

---

## 22-12-2025 Corrección de Duplicidad de Streaming entre Nodo del Grafo y LLMService

Se observó que tanto el nodo del grafo como el `LLMService` manejan lógica de streaming, lo que requiere un filtrado cuidadoso de `AIMessage` para no duplicar contenido en el historial. Se modificó `call_model_node` para usar directamente el `AIMessage` del `LLMService` en lugar de crear uno nuevo.

- **Modificación de call_model_node**: Se cambió la lógica en `kogniterm/core/agents/bash_agent.py` para append directamente el `AIMessage` recibido del `LLMService` en lugar de crear uno nuevo con contenido duplicado.
- **Eliminación de creación redundante**: Se eliminó la creación de `ai_message_for_history` para evitar duplicación de contenido en el historial, ya que el `AIMessage` del `LLMService` ya contiene el contenido completo acumulado durante el streaming.

---

## 22-12-2025 Mejora en la Validación de Secuencia de Mensajes para Evitar Tool Messages Huérfanos

Se implementó una validación más estricta en `LLMService.invoke` para filtrar mensajes de herramienta huérfanos que no siguen inmediatamente a un mensaje de asistente con `tool_calls`, corrigiendo el error "Missing corresponding tool call for tool response message" en Gemini y otros proveedores.

- **Adición de bandera in_tool_sequence**: Se introdujo una bandera `in_tool_sequence` para rastrear si los mensajes de herramienta están en una secuencia válida después de un asistente con `tool_calls`.
- **Modificación de la lógica de validación**: Se actualizó la validación de secuencia para solo incluir `tool` messages si `in_tool_sequence` es `True`, y resetear la bandera en mensajes de usuario o asistentes sin `tool_calls`.
- **Prevención de errores de API**: Esta mejora evita que secuencias inválidas como `assistant` (sin `tool_calls`) -> `tool` sean enviadas a los proveedores de LLM, que las rechazan.

---

## 22-12-2025 Manejo de Error de Secuencia de Herramientas para Recuperación de Conversación

Se agregó un manejo específico para el error "Missing corresponding tool call for tool response message" en `LLMService.invoke`, permitiendo limpiar el historial de mensajes de herramienta huérfanos y continuar la conversación sin perder el proceso.

- **Detección del error específico**: Se identifica el error de secuencia de herramientas en el bloque de manejo de excepciones.
- **Limpieza automática del historial**: Al detectar el error, se limpia el historial removiendo `ToolMessage`s huérfanos que no siguen a un `AIMessage` con `tool_calls`, preservando la conversación válida.
- **Mensaje informativo al usuario**: Se proporciona un mensaje amigable explicando la limpieza y sugiriendo repetir la solicitud si es necesario, permitiendo continuar sin interrupción.

---

## 22-12-2025 Corrección de Error de Tool Call ID Mismatch en Gemini

Se ha corregido un error crítico en el manejo de IDs de llamadas a herramientas para el modelo Gemini, donde el truncamiento del tool_call_id causaba un desajuste entre la solicitud y la respuesta, resultando en una excepción de LiteLLM.

- **Punto 1**: Se eliminó el truncamiento del tool_call_id en la conversión de ToolMessage a formato LiteLLM en `kogniterm/core/llm_service.py`, permitiendo que IDs largos generados por Gemini se mantengan consistentes.
- **Punto 2**: Se mejoró la lógica de validación de secuencia para incluir tool messages con IDs que coincidan parcialmente con los conocidos, manejando casos donde los IDs fueron truncados en sesiones anteriores.
