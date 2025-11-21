# 📝 Propuesta: Implementación de un Sistema RAG de Codebase en KogniTerm

## 1. Introducción: Potenciando el Contexto de KogniTerm con RAG

El sistema RAG (Retrieval-Augmented Generation) para el codebase permitirá a KogniTerm acceder y recuperar dinámicamente fragmentos de código relevantes del proyecto actual, utilizando estos fragmentos como contexto adicional para el LLM. Esto mejorará drásticamente la precisión, relevancia y eficiencia de las respuestas del agente, especialmente en tareas de depuración, generación de código y análisis.

Nos basaremos en el concepto de "índice de la base de código" de Kilo Code, pero adaptado a la naturaleza empaquetada y multicontexto de KogniTerm.

## 2. Componentes Clave de un Sistema RAG de Codebase para KogniTerm

Para implementar un sistema RAG robusto, necesitaremos los siguientes componentes:

### 2.1. 📚 Indexador de Codebase

*   **Función:** Recorre el directorio del proyecto, identifica archivos de código relevantes, los divide en "chunks" (fragmentos lógicos como funciones, clases, bloques de código) y genera embeddings vectoriales para cada chunk.
*   **Archivos a Indexar:** Podría configurarse para incluir archivos `.py`, `.js`, `.ts`, `.java`, `.c`, `.cpp`, `.go`, `.md`, `.json`, etc., y excluir directorios como `node_modules`, `.git`, `__pycache__`, etc.
*   **Ubicación:** Un nuevo módulo en `kogniterm/core/context/codebase_indexer.py`.

### 2.2. 📊 Base de Datos Vectorial (Vector DB)

*   **Función:** Almacena los embeddings vectoriales generados por el indexador junto con metadatos asociados (ruta del archivo, contenido original del chunk, línea de inicio, línea de fin).
*   **Características Clave:** Debe ser ligera, fácil de integrar en una aplicación empaquetada y capaz de soportar múltiples bases de datos por proyecto.
*   **Ubicación:** Un nuevo módulo de abstracción en `kogniterm/core/context/vector_db_manager.py` que interactúe con la base de datos elegida.

### 2.3. 🌐 Proveedor de Embeddings

*   **Función:** Una API o un modelo local que convierte texto (chunks de código) en vectores numéricos de alta dimensión.
*   **Flexibilidad:** Debe ser configurable para permitir diferentes proveedores (OpenAI, Gemini, Ollama, Hugging Face, etc.).
*   **Ubicación:** Extender `kogniterm/core/llm_service.py` o crear un `kogniterm/core/embeddings_service.py`.

### 2.4. 🔍 Recuperador (Retriever)

*   **Función:** Dadas una consulta (pregunta del usuario, contexto actual del agente), genera un embedding para la consulta y lo utiliza para buscar los chunks de código más semánticamente similares en la Base de Datos Vectorial.
*   **Ubicación:** Una nueva herramienta `codebase_search_tool.py` en `kogniterm/core/tools/`.

## 3. ⚙️ Opciones de Configuración en la Terminal (CLI)

La configuración debería ser intuitiva y flexible, permitiendo al usuario definir sus preferencias para cada proyecto o globalmente.

### 3.1. Comando de Configuración Global y por Proyecto

Podríamos introducir un comando `kogniterm config` o `kogniterm settings` con subcomandos:

```bash
kogniterm config set embeddings_provider openai
kogniterm config set embeddings_model text-embedding-ada-002
kogniterm config set openai_api_key sk-...

# Configuración específica para el proyecto actual
kogniterm config project set codebase_index_exclude_dirs "node_modules,dist"
```

*   **Implementación:**
    *   Un nuevo módulo `kogniterm/terminal/config_manager.py` para manejar la lectura/escritura de configuraciones.
    *   La configuración global se guardaría en un archivo de configuración en el directorio de usuario (ej., `~/.kogniterm/config.json`).
    *   La configuración por proyecto se guardaría en un archivo `.kogniterm/config.json` dentro del directorio del proyecto, sobrescribiendo la global si es necesario.

### 3.2. Configuración de Proveedores y Modelos de Embeddings

*   **Proveedor:** Una lista de opciones predefinidas (OpenAI, Gemini, Ollama, etc.).
*   **Modelo:** Para cada proveedor, una lista de modelos compatibles.
*   **API Keys:** Gestión segura de claves API (variables de entorno, archivo de configuración encriptado o prompts interactivos).

### 3.3. Configuración del Indexador

*   **Archivos a incluir/excluir:** Patrones glob para incluir/excluir archivos y directorios durante la indexación.
*   **Tamaño de Chunk:** Configurar el tamaño máximo de los fragmentos de código.
*   **Estrategia de Chunking:** (Opcional) Definir cómo se dividen los archivos (por función, por clase, por líneas, etc.).

## 4. 🗄️ Estrategias de Gestión de la Base de Datos Vectorial

Dado que KogniTerm es una aplicación empaquetada y cada directorio es un proyecto independiente, necesitamos una solución de base de datos vectorial que sea ligera, integrada y local.

### 4.1. Opción 1: Base de Datos Vectorial Integrada y Basada en Archivos (Recomendada)

*   **Base de Datos Sugeridas:**
    *   **ChromaDB (modo persistente):** Es una base de datos vectorial de código abierto, ligera y que puede funcionar completamente basada en archivos. Es fácil de instalar y gestionar.
    *   **FAISS (Facebook AI Similarity Search):** Una biblioteca para la búsqueda eficiente de similitud de vectores. Requiere un poco más de gestión para la persistencia, pero es extremadamente rápida para la búsqueda.
*   **Estrategia por Proyecto:**
    *   Cada directorio de proyecto tendría su propia instancia de la Base de Datos Vectorial persistente.
    *   Se crearía una subcarpeta oculta, por ejemplo, `.kogniterm/vector_db/`, dentro de cada directorio de proyecto. Aquí se almacenarían los archivos de la Base de Datos Vectorial (ej., los archivos de ChromaDB).
    *   Esto garantiza el aislamiento total del contexto entre proyectos y facilita el borrado o la copia de proyectos.
*   **Ventajas:**
    *   **Portabilidad:** El directorio del proyecto es autocontenido, fácil de mover o compartir.
    *   **Aislamiento:** Un proyecto no interfiere con el índice de otro.
    *   **Facilidad de Instalación:** No requiere servidores externos ni configuraciones complejas por parte del usuario.
*   **Desventajas:** El rendimiento podría ser un factor en proyectos *extremadamente* grandes (aunque poco probable para la mayoría de los casos de uso).

### 4.2. Opción 2: Base de Datos Vectorial Ligera en Proceso (Menos Recomendada para Persistencia)

*   **Base de Datos Sugeridas:** `Annoy` (Approximate Nearest Neighbors Oh Yeah), `Hnswlib`.
*   **Estrategia:** La Base de Datos Vectorial se cargaría en memoria al iniciar KogniTerm en un proyecto y se descartaría al finalizar. Para la persistencia, los embeddings y metadatos se guardarían en archivos JSON o SQLite y se recargarían.
*   **Ventajas:** Muy rápida en memoria.
*   **Desventajas:** Gestión de persistencia manual, potencialmente más lenta para cargar/guardar, mayor consumo de RAM para proyectos grandes si no se gestiona cuidadosamente.

## 5. 🔄 Flujo de Trabajo del Sistema RAG

1.  **Inicialización del Proyecto:**
    *   Al abrir KogniTerm en un nuevo directorio de proyecto, se detecta la ausencia del índice de codebase.
    *   KogniTerm pregunta al usuario si desea indexar el proyecto (o lo hace automáticamente si está configurado).
    *   El `Codebase Indexer` se ejecuta, genera embeddings y los almacena en la `Vector DB` local (`.kogniterm/vector_db/`).
2.  **Actualización del Índice:**
    *   Se implementa un mecanismo para detectar cambios en los archivos (observador de archivos como `watchdog`) o un comando manual `kogniterm index refresh`.
    *   Solo se reindexan los archivos modificados o nuevos, para mayor eficiencia.
3.  **Consulta RAG (durante la interacción del agente):**
    *   Cuando el agente necesita contexto de código (ej., para responder una pregunta sobre una función, depurar un error), utiliza la herramienta `codebase_search`.
    *   El `Recuperador` genera un embedding de la consulta y busca los `N` chunks de código más relevantes en la `Vector DB` del proyecto.
    *   Los chunks recuperados se añaden al contexto del LLM como parte del `SystemMessage` o en un formato estructurado.
    *   El LLM utiliza este contexto de código para generar una respuesta más informada.

## 6. 🛠️ Consideraciones de Implementación

*   **Dependencias:** Asegurarse de que las dependencias de la Base de Datos Vectorial (ej., `chromadb`) sean fáciles de instalar para el usuario final (posiblemente incluyéndolas en `requirements.txt` o como una dependencia opcional).
*   **Manejo de Errores:** Robustecer la indexación para manejar archivos corruptos o errores en la generación de embeddings.
*   **Rendimiento:** Optimizar el proceso de indexación para proyectos grandes (indexación incremental, procesamiento en segundo plano).
*   **Seguridad:** Si se usa un proveedor de embeddings en la nube, asegurar que las claves API se manejen de forma segura y nunca se expongan.
*   **UX/UI:** Proporcionar retroalimentación clara al usuario durante la indexación y la recuperación.

## 7. Conclusión

La implementación de un sistema RAG de codebase transformaría a KogniTerm en un asistente mucho más competente y autónomo en el manejo de proyectos de código. Al combinar la configuración flexible en la terminal con una gestión de base de datos vectorial local y por proyecto, aseguramos una solución potente, integrada y fácil de usar.
