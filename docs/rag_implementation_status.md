# 📝 Estado de la Implementación del Sistema RAG en KogniTerm

Este documento resume el progreso realizado en la integración del sistema RAG (Retrieval-Augmented Generation) en KogniTerm hasta la fecha.

## 🌟 Visión General del Proyecto

El objetivo es integrar un sistema RAG de codebase en KogniTerm que permita:
1.  **Configurar** proveedores y modelos de embeddings desde la terminal.
2.  **Indexar** el código fuente de un proyecto en una base de datos vectorial local.
3.  **Recuperar** fragmentos de código relevantes para enriquecer el contexto del LLM.
4.  Funcionar de manera **autocontenida** por proyecto/directorio.

## ✅ Fases Completadas

Hemos completado exitosamente las Fases 1 a 5 del plan de implementación.

### FASE 1: ⚙️ Configuración CLI y Gestión de Archivos de Configuración
*   **`kogniterm/core/config.py`**:
    *   Se añadieron campos de configuración específicos para RAG (`embeddings_provider`, `embeddings_model`, `codebase_index_exclude_dirs`, `codebase_index_include_patterns`, `codebase_chunk_size`, `codebase_chunk_overlap`).
    *   Se implementó la lógica para cargar configuraciones desde archivos JSON globales (`~/.kogniterm/config.json`) y por proyecto (`.kogniterm/config.json`), utilizando `pydantic-settings` y una fuente de configuración JSON personalizada.
    *   Se añadieron métodos `save_project_config()` y `save_global_config()` para persistir las configuraciones.
*   **`kogniterm/terminal/meta_command_processor.py`**:
    *   Se modificó para manejar los comandos CLI `%config set <clave> <valor>` y `%config project set <clave> <valor>`, permitiendo a los usuarios establecer y persistir configuraciones.
    *   Se actualizó el mensaje de ayuda (`%help`) para incluir estos nuevos comandos.

### FASE 2: 🌐 Servicio de Embeddings y Abstracción de Proveedores
*   **`kogniterm/core/embeddings_service.py`**:
    *   Se creó un nuevo módulo con la clase `EmbeddingsService`.
    *   Esta clase proporciona una interfaz unificada para generar embeddings utilizando `litellm`, soportando proveedores como OpenAI, Google Gemini y Ollama, y leyendo la configuración desde `settings`.
*   **`kogniterm/core/llm_service.py`**:
    *   Se integró el `EmbeddingsService` en el constructor de `LLMService`, asegurando que el servicio de embeddings esté disponible para otros componentes.

### FASE 3: 📚 Indexador de Codebase (Chunking y Embedding)
*   **`kogniterm/core/context/codebase_indexer.py`**:
    *   Se creó un nuevo módulo con la clase `CodebaseIndexer`.
    *   Implementa la lógica para recorrer el directorio del proyecto, listar archivos de código (respetando patrones de inclusión/exclusión de `settings`).
    *   Divide los archivos en "chunks" lógicos con solapamiento, utilizando `settings.codebase_chunk_size` y `settings.codebase_chunk_overlap`.
    *   Orquesta la generación de embeddings para cada chunk utilizando el `EmbeddingsService`.

### FASE 4: 📊 Gestión de la Base de Datos Vectorial (ChromaDB)
*   **`kogniterm/core/context/vector_db_manager.py`**:
    *   Se creó un nuevo módulo con la clase `VectorDBManager`.
    *   Gestiona la inicialización de una instancia de ChromaDB en modo persistente para cada proyecto (en `.kogniterm/vector_db/`).
    *   Proporciona métodos para añadir chunks y sus embeddings a la base de datos, y para realizar búsquedas de similitud (`search`).

### FASE 5: 🔍 Herramienta de Recuperación (Retriever Tool)
*   **`kogniterm/core/tools/codebase_search_tool.py`**:
    *   Se creó un nuevo módulo con la clase `CodebaseSearchTool`, que hereda de `BaseTool` de LangChain.
    *   Permite al agente realizar búsquedas de fragmentos de código relevantes en la base de datos vectorial del proyecto.
    *   Utiliza el `EmbeddingsService` para generar embeddings de la consulta y el `VectorDBManager` para la búsqueda.
    *   Formatea los resultados de la búsqueda en una cadena de texto útil para el contexto del LLM.

## 🚧 Fases Pendientes (Fase 6: Integración y Flujo de Trabajo RAG)

Actualmente estamos trabajando en la Fase 6, que es la integración final de todos los componentes.

### Tareas Pendientes:

1.  **Integración en `kogniterm/terminal/terminal.py` y `kogniterm/terminal/kogniterm_app.py`**:
    *   **Detección y solicitud de indexación al inicio**: Al iniciar KogniTerm en un proyecto, si no hay un índice de codebase, se le preguntará al usuario si desea crearlo. Esta lógica ya está parcialmente implementada en `_main_async()` en `kogniterm/terminal/terminal.py`.
    *   **Pendiente de corregir la firma del `__init__` de `KogniTermApp` y pasar `codebase_indexer` y `vector_db_manager`**: Hubo problemas recurrentes con la edición de la firma del `__init__` en `kogniterm/terminal/kogniterm_app.py` y la inicialización de `MetaCommandProcessor` debido a fallos con `replace_regex`. Esto necesita una corrección precisa.

2.  **Integración de RAG en el agente (modificar `kogniterm/core/llm_service.py` o la lógica de toma de decisiones del agente)**:
    *   Se necesita implementar la lógica para que el agente identifique cuándo una consulta del usuario o una tarea podría beneficiarse de la recuperación de código.
    *   El agente deberá invocar la `codebase_search_tool` con una consulta relevante.
    *   Los resultados de la búsqueda de la herramienta se inyectarán en el contexto del LLM (como parte del `SystemMessage` o un `ToolMessage`) antes de generar la respuesta final.

## ⚠️ Problemas Recurrentes Identificados

*   **Error de "Máximo de Tokens por Minuto"**: Se ha reportado un error recurrente de límite de tokens por minuto. Esto sugiere la necesidad de una gestión de tasas más robusta o ajustes en la configuración de `litellm`.
*   **Error en la Compresión del Historial**: Se ha reportado un problema con la función de compresión del historial. Esto necesita depuración en `kogniterm/core/llm_service.py` (método `summarize_conversation_history`).
*   **Problemas con `replace_regex` en `advanced_file_editor`**: Se han experimentado dificultades para aplicar cambios precisos a líneas específicas usando `replace_regex`, lo que ha llevado a errores de sintaxis y a la imposibilidad de aplicar modificaciones cruciales. Esto ha sido el principal obstáculo para la integración de los parámetros RAG en `KogniTermApp`.

## Próximos Pasos

1.  **Corregir la firma del `__init__` en `kogniterm/terminal/kogniterm_app.py` y la inicialización de `MetaCommandProcessor`**: Utilizar una estrategia de edición más robusta (lectura completa, modificación en memoria, reescritura) para asegurar que estos cambios se apliquen correctamente.
2.  **Abordar el error de "Máximo de Tokens por Minuto"**: Investigar opciones de `rate limiting` en `litellm` o implementar pausas explícitas.
3.  **Depurar el error de la Compresión del Historial**: Revisar `summarize_conversation_history` en `kogniterm/core/llm_service.py`.
4.  Una vez resueltos los problemas anteriores, continuar con la **integración de RAG en el agente** en `kogniterm/core/llm_service.py` o la lógica de toma de decisiones del agente.
