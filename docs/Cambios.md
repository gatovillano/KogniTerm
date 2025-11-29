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

Se ha reforzado la instrucción en el prompt del sistema para evitar que el agente explique los comandos de terminal en su respuesta de texto, eliminando así la duplicidad con el panel de confirmación.

- **Punto 1**: Se modificó la instrucción en `kogniterm/core/agents/bash_agent.py` para ser mucho más estricta y explícita ("NO expliques comandos de terminal... Esto es CRÍTICO"), indicando al agente que solo mencione la acción general y deje la explicación técnica al sistema automático.

- **Punto 2**: Se corrigió un error lógico en `CommandApprovalHandler.py` que causaba la duplicación exacta del texto de la explicación. El problema era que el bucle acumulaba tanto los fragmentos de texto transmitidos (streaming) como el mensaje final completo (`AIMessage`) que `llm_service` emite al final. Se añadió una condición para ignorar el contenido del `AIMessage` final si ya se había acumulado texto mediante streaming.
