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
- **Punto 2**: Se eliminó el código relacionado con el spinner de carga en `kogniterm/terminal/agent_interaction_manager.py` para limpiar la salida y evitar posibles conflictos de hilos.
