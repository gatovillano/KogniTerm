# 🗺️ Plan de Implementación RAG de Codebase para KogniTerm (con Agentes)

Este plan desglosa la implementación del sistema RAG en KogniTerm en fases manejables, cada una con un objetivo claro y un prompt diseñado para el orquestador de Kilo Code.

## 🌟 Visión General del Proyecto

El objetivo es integrar un sistema RAG de codebase en KogniTerm que permita:
1.  **Configurar** proveedores y modelos de embeddings desde la terminal.
2.  **Indexar** el código fuente de un proyecto en una base de datos vectorial local.
3.  **Recuperar** fragmentos de código relevantes para enriquecer el contexto del LLM.
4.  Funcionar de manera **autocontenida** por proyecto/directorio.

---

## FASE 1: ⚙️ Configuración CLI y Gestión de Archivos de Configuración

**Objetivo:** Implementar la lógica para que KogniTerm pueda guardar y cargar configuraciones globales y por proyecto desde la terminal.

**Tareas Clave:**
*   Crear un módulo `config_manager.py` para manejar la lectura/escritura de configuraciones JSON.
*   Implementar comandos CLI para `kogniterm config set <clave> <valor>` y `kogniterm config project set <clave> <valor>`.
*   Asegurar que la configuración por proyecto sobrescriba la global.
*   Manejo básico de claves API (ej., guardar en el archivo de config o sugerir variables de entorno).

**Módulos Involucrados:**
*   `kogniterm/terminal/config_manager.py` (nuevo)
*   Posiblemente modificar `kogniterm/main.py` para integrar los comandos CLI.

**Prompt para el Orquestador de Kilo Code (Fase 1):**

```
"Implementa la Fase 1 del sistema RAG de codebase para KogniTerm. El objetivo es crear un sistema robusto de gestión de configuración CLI. Necesitas desarrollar un nuevo módulo `kogniterm/terminal/config_manager.py` que se encargue de leer y escribir configuraciones en formato JSON. Debe soportar configuraciones globales (en `~/.kogniterm/config.json`) y configuraciones específicas por proyecto (en `.kogniterm/config.json` dentro del directorio actual del proyecto), donde las configuraciones del proyecto sobrescriben las globales.

Además, integra comandos CLI `kogniterm config set <clave> <valor>` y `kogniterm config project set <clave> <valor>` para permitir al usuario establecer estas configuraciones. Asegúrate de que el manejo de claves API sea seguro, sugiriendo el uso de variables de entorno o guardándolas de forma básica en el archivo de configuración.

Considera la estructura de directorios existente de KogniTerm y cómo se integraría este nuevo módulo en la aplicación principal."
```

---

## FASE 2: 🌐 Servicio de Embeddings y Abstracción de Proveedores

**Objetivo:** Crear un servicio en KogniTerm que pueda generar embeddings utilizando diferentes proveedores (OpenAI, Gemini, Ollama) de manera abstracta.

**Tareas Clave:**
*   Crear un módulo `embeddings_service.py` con una interfaz común para generar embeddings.
*   Implementar adaptadores para al menos dos proveedores (ej., OpenAI y Gemini).
*   El servicio debe leer la configuración del proveedor y modelo desde `config_manager`.
*   Manejar la inicialización de clientes de API para cada proveedor.

**Módulos Involucrados:**
*   `kogniterm/core/embeddings_service.py` (nuevo)
*   `kogniterm/core/llm_service.py` (posible extensión o referencia)
*   `kogniterm/terminal/config_manager.py` (usado para leer configuración)

**Prompt para el Orquestador de Kilo Code (Fase 2):**

```
"Desarrolla la Fase 2 del sistema RAG de codebase para KogniTerm. El objetivo es crear un `Embeddings Service` abstracto. Crea un nuevo módulo `kogniterm/core/embeddings_service.py` que proporcione una interfaz unificada para generar embeddings.

Este servicio debe ser capaz de:
1.  Leer la configuración del proveedor de embeddings (ej., 'openai', 'gemini', 'ollama') y el modelo (ej., 'text-embedding-ada-002', 'embedding-001') a través del `config_manager` implementado en la Fase 1.
2.  Implementar adaptadores para al menos OpenAI y Google Gemini, manejando la inicialización de sus respectivos clientes de API (ej., `openai.OpenAI()`, `google.generativeai.GenerativeModel()`).
3.  La función principal `generate_embeddings(text: list[str]) -> list[list[float]]` debe devolver una lista de vectores de embeddings para una lista de textos de entrada.
4.  Asegúrate de manejar posibles errores de conexión o autenticación de forma elegante."
```

---

## FASE 3: 📚 Indexador de Codebase (Chunking y Embedding)

**Objetivo:** Implementar la lógica para recorrer un directorio, dividir archivos de código en "chunks" y generar embeddings para cada uno.

**Tareas Clave:**
*   Crear un módulo `codebase_indexer.py`.
*   Función para listar archivos de código en un directorio, respetando exclusiones configuradas (desde `config_manager`).
*   Implementar una estrategia de "chunking" básica para archivos de texto/código (ej., dividir por líneas con un tamaño máximo, o por delimitadores simples como funciones/clases si es un archivo Python).
*   Utilizar el `Embeddings Service` (de la Fase 2) para generar embeddings para cada chunk.
*   Estructurar los datos del chunk (contenido, ruta del archivo, líneas de inicio/fin) para su almacenamiento.

**Módulos Involucrados:**
*   `kogniterm/core/context/codebase_indexer.py` (nuevo)
*   `kogniterm/core/embeddings_service.py` (usado)
*   `kogniterm/terminal/config_manager.py` (usado para exclusiones)

**Prompt para el Orquestador de Kilo Code (Fase 3):**

```
"Procede con la Fase 3 del sistema RAG de codebase para KogniTerm. El objetivo es desarrollar el `Codebase Indexer`. Crea un nuevo módulo `kogniterm/core/context/codebase_indexer.py`.

Este módulo debe incluir:
1.  Una función `list_code_files(project_path: str) -> list[str]` que recorra el `project_path` y devuelva una lista de rutas de archivos de código. Debe respetar las listas de exclusión de directorios y tipos de archivos configuradas a través del `config_manager` (ej., `node_modules`, `.git`, `__pycache__`).
2.  Una función `chunk_file(file_path: str) -> list[dict]` que lea un archivo de código y lo divida en 'chunks' lógicos. Cada chunk debe ser un diccionario con `{'content': '...', 'file_path': '...', 'start_line': ..., 'end_line': ...}`. Para empezar, una estrategia simple de división por líneas o párrafos es suficiente.
3.  Una función `index_project(project_path: str)` que orqueste el proceso: liste archivos, los divida en chunks y, para cada chunk, genere su embedding utilizando el `Embeddings Service` desarrollado en la Fase 2. El output de esta función debe ser una lista de diccionarios, donde cada diccionario contenga el chunk y su embedding."
```

---

## FASE 4: 📊 Gestión de la Base de Datos Vectorial (ChromaDB)

**Objetivo:** Integrar ChromaDB en modo persistente para almacenar los embeddings y metadatos por cada proyecto.

**Tareas Clave:**
*   Crear un módulo `vector_db_manager.py` que abstraiga la interacción con ChromaDB.
*   Funciones para inicializar una colección de ChromaDB en una ruta de directorio específica (ej., `.kogniterm/vector_db/`).
*   Funciones para añadir chunks (contenido, metadatos, embeddings) a la base de datos.
*   Funciones para buscar los K vecinos más cercanos (chunks) dada una consulta de embedding.
*   Asegurar que cada proyecto tenga su propia base de datos aislada.

**Módulos Involucrados:**
*   `kogniterm/core/context/vector_db_manager.py` (nuevo)
*   `kogniterm/core/context/codebase_indexer.py` (usado para obtener chunks y embeddings)

**Prompt para el Orquestador de Kilo Code (Fase 4):**

```
"Continúa con la Fase 4 del sistema RAG de codebase para KogniTerm. El objetivo es implementar la gestión de la Base de Datos Vectorial utilizando ChromaDB en modo persistente. Crea un nuevo módulo `kogniterm/core/context/vector_db_manager.py`.

Este módulo debe proporcionar una clase `VectorDBManager` con los siguientes métodos:
1.  `__init__(self, project_path: str)`: Inicializa la instancia de ChromaDB para el `project_path` dado. La base de datos debe persistir en una subcarpeta oculta como `.kogniterm/vector_db/` dentro del directorio del proyecto.
2.  `add_chunks(self, chunks: list[dict], embeddings: list[list[float]])`: Recibe una lista de diccionarios de chunks (con `content`, `file_path`, etc.) y sus correspondientes embeddings. Debe añadir estos datos a la colección de ChromaDB.
3.  `search(self, query_embedding: list[float], k: int = 5) -> list[dict]`: Realiza una búsqueda de similitud en la base de datos con un `query_embedding` y devuelve los `k` chunks más relevantes como diccionarios (incluyendo `content` y `metadatos`).

Asegúrate de que cada instancia de `VectorDBManager` sea completamente independiente para cada `project_path`, garantizando el aislamiento de las bases de datos vectoriales entre proyectos."
```

---

## FASE 5: 🔍 Herramienta de Recuperación (Retriever Tool)

**Objetivo:** Desarrollar una herramienta que el agente pueda usar para buscar fragmentos de código relevantes en la Base de Datos Vectorial.

**Tareas Clave:**
*   Crear una nueva herramienta `codebase_search_tool.py`.
*   La herramienta debe tomar una consulta de texto como entrada.
*   Utilizar el `Embeddings Service` (de la Fase 2) para generar un embedding de la consulta.
*   Utilizar el `VectorDBManager` (de la Fase 4) para buscar los chunks más relevantes.
*   Formatear los resultados de la búsqueda para que sean útiles como contexto para el LLM.

**Módulos Involucrados:**
*   `kogniterm/core/tools/codebase_search_tool.py` (nuevo)
*   `kogniterm/core/embeddings_service.py` (usado)
*   `kogniterm/core/context/vector_db_manager.py` (usado)

**Prompt para el Orquestador de Kilo Code (Fase 5):**

```
"Implementa la Fase 5 del sistema RAG de codebase para KogniTerm. El objetivo es crear una nueva herramienta llamada `codebase_search_tool.py` dentro de `kogniterm/core/tools/`.

Esta herramienta debe ser una función (o clase de herramienta) que:
1.  Acepte un argumento `query: str` (la consulta de búsqueda del agente) y `k: int` (número de resultados a devolver).
2.  Utilice el `Embeddings Service` (de la Fase 2) para generar un embedding vectorial de la `query`.
3.  Inicialice o acceda a una instancia del `VectorDBManager` (de la Fase 4) para el proyecto actual.
4.  Use el método `search` del `VectorDBManager` con el embedding de la consulta para recuperar los `k` chunks de código más relevantes.
5.  Formatee los resultados de la búsqueda (ej., concatenando el contenido de los chunks con su `file_path` y `start_line`) en una cadena de texto clara que pueda ser fácilmente incorporada al contexto de un LLM.
6.  La herramienta debe devolver esta cadena formateada como su resultado."
```

---

## FASE 6: 🔄 Integración y Flujo de Trabajo RAG

**Objetivo:** Integrar todas las fases anteriores en el flujo principal de KogniTerm y habilitar la indexación automática/manual y el uso del RAG por el agente.

**Tareas Clave:**
*   Modificar el bucle principal o el `AgentState` para detectar si un proyecto ha sido indexado y ofrecer/realizar la indexación inicial.
*   Implementar un mecanismo para la actualización incremental del índice (ej., al guardar archivos o con un comando `kogniterm index refresh`).
*   Modificar la lógica del `llm_service` o del `agent_state` para que, antes de hacer una llamada al LLM para ciertas tareas, considere usar la `codebase_search_tool` para enriquecer el contexto.
*   Asegurar que los resultados de la `codebase_search_tool` se inyecten de forma estructurada y útil en el `SystemMessage` o `UserMessage` para el LLM.

**Módulos Involucrados:**
*   `kogniterm/main.py`
*   `kogniterm/core/agent_state.py`
*   `kogniterm/core/llm_service.py`
*   `kogniterm/terminal/config_manager.py`
*   `kogniterm/core/context/codebase_indexer.py`
*   `kogniterm/core/context/vector_db_manager.py`
*   `kogniterm/core/tools/codebase_search_tool.py`

**Prompt para el Orquestador de Kilo Code (Fase 6):**

```
"Finaliza la implementación del sistema RAG de codebase para KogniTerm con la Fase 6: Integración y Flujo de Trabajo RAG. El objetivo es integrar todos los componentes desarrollados en las fases anteriores en el flujo principal de KogniTerm.

Necesitas:
1.  Modificar `kogniterm/main.py` o `kogniterm/core/agent_state.py` para:
    *   Detectar si el proyecto actual tiene un índice de codebase (`.kogniterm/vector_db/`).
    *   Si no lo tiene, preguntar al usuario si desea indexarlo o indexarlo automáticamente si la configuración lo permite, utilizando el `codebase_indexer.py`.
    *   Implementar un comando CLI `kogniterm index refresh` para reindexar el proyecto manualmente.
2.  Modificar `kogniterm/core/llm_service.py` o la lógica de toma de decisiones del agente (si existe un módulo específico para ello) para:
    *   Identificar cuándo una consulta del usuario o una tarea del agente podría beneficiarse de la recuperación de código.
    *   En esos casos, el agente debe invocar la `codebase_search_tool` (de la Fase 5) con una consulta relevante.
    *   Inyectar los resultados de la búsqueda de la herramienta (`codebase_search_tool`) en el contexto del LLM (ej., como parte del `SystemMessage` o como un `ToolMessage` específico) antes de generar la respuesta final.
3.  Asegurarse de que el flujo general del agente sea coherente y que el contexto de código recuperado mejore la calidad de las respuestas del LLM sin sobrecargarlo."
```
