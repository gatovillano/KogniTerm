# Visión General del Proyecto KogniTerm

## 🎯 Propósito y Filosofía

**KogniTerm** redefine la interacción entre desarrolladores y sistemas operativos. No es simplemente un "chat con la terminal", sino un **Entorno de Desarrollo Agéntico (ADE)** que vive en tu CLI.

Su filosofía se basa en tres pilares:

1. **Especialización**: Un solo agente no puede hacerlo todo bien. KogniTerm orquesta un equipo de especialistas (Investigador, Desarrollador, Operador).
2. **Universalidad**: No atarse a un solo proveedor de IA. Gracias a su motor de parseo híbrido, KogniTerm otorga capacidades de uso de herramientas a modelos que nativamente no las tienen.
3. **Transparencia y Control**: El usuario siempre tiene la última palabra. Nada se ejecuta sin supervisión (a menos que tú lo decidas).

## 🏗 Arquitectura del Sistema

La arquitectura de KogniTerm es modular, extensible y está diseñada sobre **LangGraph** para gestionar flujos de trabajo complejos y con estado.

### 1. El Núcleo Multi-Agente (`core/agents/`)

El "cerebro" de KogniTerm no es monolítico. Se divide en roles especializados:

* **🤖 BashAgent (El Orquestador)**:
  * Es el punto de entrada.
  * Maneja la interacción directa con el usuario.
  * Decide si una tarea es simple (ejecutar un comando) o requiere delegación.
  * *Responsabilidad*: Operación del sistema y gestión del flujo.

* **🕵️ ResearcherAgent (El Detective)**:
  * Especialista en lectura y análisis.
  * Tiene herramientas de "solo lectura" (read_file, search, grep).
  * Genera reportes en Markdown y explicaciones detalladas.
  * *Responsabilidad*: Comprensión profunda sin riesgo de efectos secundarios.

* **👨‍💻 CodeAgent (El Desarrollador)**:
  * Especialista en modificación de código.
  * Sigue principios de ingeniería de software (validación, atomicidad).
  * Utiliza herramientas de edición precisa y verificación de sintaxis.
  * *Responsabilidad*: Escritura de código segura y de alta calidad.

### 2. Motor de Parseo Universal (`llm_service.py`)

Este componente es lo que hace a KogniTerm único. Actúa como un "traductor universal" entre la intención del LLM y la ejecución de código.

* **Soporte Nativo**: Para modelos con API de `tool_calls` (OpenAI, Gemini, Anthropic).
* **Text-to-Tool Parsing**: Para modelos que solo generan texto (DeepSeek, Llama, modelos locales). Detecta patrones (JSON, XML, llamadas tipo función) dentro del texto libre y los convierte en ejecuciones estructuradas.
* **Normalización**: Unifica las respuestas de diferentes proveedores en un formato estándar para los agentes.

### 3. Capa de Ejecución (`terminal/`)

* **Terminal Interactiva (`terminal.py`)**: Interfaz rica (UI) construida con `prompt_toolkit` y `rich`. Maneja autocompletado, historial y renderizado de Markdown.
* **Ejecutor Seguro (`command_executor.py`)**: Sandbox para la ejecución de comandos de shell. Captura stdout/stderr en tiempo real y maneja interacciones (inputs de usuario, contraseñas).

### 4. Sistema RAG Local (`core/context/`)

KogniTerm indexa tu base de código localmente usando embeddings (ChromaDB). Esto permite a los agentes realizar búsquedas semánticas ("¿Dónde se maneja la autenticación?") en lugar de solo búsquedas por nombre de archivo, proporcionando un contexto mucho más rico.

## 🔄 Flujo de Trabajo Típico

1. **Entrada**: El usuario escribe: *"Analiza por qué falla el login y arréglalo"*.
2. **Orquestación (BashAgent)**:
    * Detecta que es una tarea compleja.
    * Invoca a **ResearcherAgent**: *"Investiga el flujo de login y busca errores"*.
3. **Investigación (ResearcherAgent)**:
    * Lee archivos, busca en logs, entiende el problema.
    * Devuelve un reporte: *"El error está en `auth.py`, línea 45. Falta un manejo de excepción"*.
4. **Desarrollo (CodeAgent)**:
    * BashAgent recibe el reporte y delega a **CodeAgent**: *"Aplica el fix sugerido en `auth.py`"*.
    * CodeAgent lee el archivo, aplica el parche y verifica la sintaxis.
5. **Confirmación**:
    * El sistema muestra el `diff` al usuario.
    * El usuario aprueba.
6. **Ejecución**: Se aplican los cambios.

## 🛡 Seguridad

* **Human-in-the-Loop**: Confirmación obligatoria para herramientas con efectos secundarios (escritura, ejecución).
* **Validación de Herramientas**: Cada herramienta tiene esquemas estrictos (Pydantic) para validar argumentos antes de la ejecución.
* **Aislamiento**: Las dependencias se gestionan preferiblemente vía `pipx` para no contaminar el sistema global.
