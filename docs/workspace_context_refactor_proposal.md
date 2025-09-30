# Propuesta de Refactorización: WorkspaceContext de KogniTerm

## 1. Introducción

Este documento detalla una propuesta de refactorización para la clase `WorkspaceContext` en KogniTerm. El objetivo es optimizar su lógica para que sea más similar a la estrategia de `WorkspaceContext` de Gemini CLI, enfocándose en la gestión de directorios y delegando responsabilidades de análisis y procesamiento a otros módulos. Esto busca mejorar la claridad, la modularidad y la mantenibilidad del código.

## 2. Análisis del `WorkspaceContext` Actual de KogniTerm

El `WorkspaceContext` actual de KogniTerm (`kogniterm/core/context/workspace_context.py`) es una clase robusta que integra una amplia gama de funcionalidades relacionadas con el contexto del proyecto, incluyendo:

*   Gestión de directorios (`directories`).
*   Observación del sistema de archivos (`file_system_watcher`).
*   Gestión de patrones de ignorado (`ignore_pattern_manager`).
*   Análisis de estructura de carpetas (`folder_structure_analyzer`).
*   Análisis de archivos de configuración (`config_file_analyzer`).
*   Interacción con Git (`git_interaction_module`).
*   Gestión de rutas (`path_manager`).
*   Indexación de contenido (`context_indexer`).
*   Construcción de contexto para LLM (`llm_context_builder`).
*   Referencia al servicio LLM (`llm_service_ref`).

Aunque esta integración centralizada ofrece un control exhaustivo, también introduce una alta cohesión y una complejidad considerable en una única clase. Además, se ha observado que muchos módulos operan principalmente sobre el primer directorio de la lista `directories`, lo que puede ser inconsistente con la idea de un "espacio de trabajo" que abarca múltiples directorios con igual importancia.

## 3. Estrategia de `WorkspaceContext` de Gemini CLI (Referencia)

El `WorkspaceContext` de Gemini CLI (`packages/core/src/utils/workspaceContext.ts`) es más simple y se enfoca principalmente en:

*   Gestionar un conjunto de directorios (`Set<string>`) para asegurar la unicidad.
*   Añadir y eliminar directorios.
*   Validar la existencia y tipo de los directorios.
*   Comprobar si una ruta dada está dentro de los directorios del espacio de trabajo.
*   Notificar a los oyentes cuando los directorios cambian.

Su rol es más el de un "contenedor" o "gestor de colecciones de directorios", delegando las responsabilidades de análisis de contenido, Git, configuración, etc., a otras capas o módulos.

## 4. Propuesta de Refactorización para KogniTerm

La propuesta es refactorizar el `WorkspaceContext` de KogniTerm para que se alinee más con el enfoque de Gemini CLI, convirtiéndolo en un gestor de directorios más puro y delegando las responsabilidades de análisis y procesamiento a otras clases.

### 4.1. Responsabilidades Centrales del Nuevo `WorkspaceContext`

El `WorkspaceContext` refactorizado se centrará en las siguientes responsabilidades principales:

*   **Gestión de Directorios:**
    *   Almacenar una colección de directorios (utilizando un `Set` para unicidad y eficiencia).
    *   Añadir y eliminar directorios.
    *   Validar la existencia y tipo de los directorios al añadirlos.
    *   Proporcionar métodos para obtener la lista de directorios.
*   **Validación de Rutas:**
    *   Determinar si una ruta de archivo o directorio dada se encuentra dentro de cualquiera de los directorios gestionados por el `WorkspaceContext`.
*   **Notificación de Cambios:**
    *   Implementar un mecanismo de notificación (`onDirectoriesChanged`) para que otras partes del sistema puedan reaccionar cuando la colección de directorios del workspace cambie.

### 4.2. Delegación de Responsabilidades

Las responsabilidades actualmente dentro de `WorkspaceContext` que no son directamente la gestión de directorios se delegarán a otras clases o a una nueva capa de orquestación.

*   **Módulos de Análisis de Contexto (Git, Config, Estructura de Carpetas, Indexación):**
    *   Estos módulos (`IgnorePatternManager`, `FolderStructureAnalyzer`, `ConfigFileAnalyzer`, `GitInteractionModule`, `ContextIndexer`, `LLMContextBuilder`) ya existen como clases separadas.
    *   La refactorización implicará que estas clases sean inicializadas y gestionadas por una nueva clase "ContextOrchestrator" o "ProjectManager", que recibirá los directorios del `WorkspaceContext` y los pasará a los módulos relevantes.
    *   Cada uno de estos módulos operará sobre los directorios proporcionados por el `WorkspaceContext`.

*   **Observación del Sistema de Archivos (`FileSystemWatcher`):**
    *   El `FileSystemWatcher` seguirá siendo una clase separada.
    *   El "ContextOrchestrator" o "ProjectManager" será el encargado de inicializar el `FileSystemWatcher` y registrar los "observadores" de cambios de archivo (por ejemplo, un `GitChangeObserver`, un `ConfigChangeObserver`) que reaccionarán a los eventos y actualizarán los módulos de contexto correspondientes.

### 4.3. Cambios Propuestos en la Clase `WorkspaceContext`

1.  **Cambiar `directories` de `List[Path]` a `Set[Path]`:** Esto garantizará la unicidad y mejorará el rendimiento de las operaciones de búsqueda y adición.
2.  **Eliminar referencias directas a módulos de contexto:** Eliminar atributos como `file_system_watcher`, `ignore_pattern_manager`, `folder_structure_analyzer`, `config_file_analyzer`, `git_interaction_module`, `context_indexer`, `llm_context_builder`, `llm_service_ref`, `event_loop`.
3.  **Simplificar el constructor:** El constructor solo recibirá el directorio inicial y, opcionalmente, directorios adicionales.
4.  **Métodos `addDirectory` y `removeDirectory`:** Asegurarse de que estos métodos gestionen correctamente el `Set` de directorios y notifiquen los cambios.
5.  **Método `isPathWithinWorkspace`:** Mantener su funcionalidad actual, pero operando sobre el `Set` de directorios.
6.  **Método `onDirectoriesChanged`:** Mantener el mecanismo de callbacks para notificar a los suscriptores.
7.  **Eliminar métodos relacionados con la inicialización de módulos internos:** `_initialize_modules`, `_reinitialize_ignore_patterns_and_folder_structure`, `_update_folder_structure`, `handle_file_system_event`, `_start_file_system_watcher`, `_stop_file_system_watcher`, `register_llm_context_builder`, `set_llm_service_ref`, `get_conversation_history`.

## 5. Nueva Clase: `ContextOrchestrator` (o similar)

Se introducirá una nueva clase, por ejemplo, `ContextOrchestrator`, que será responsable de:

*   Crear e inicializar el `WorkspaceContext`.
*   Crear e inicializar todos los módulos de contexto (`IgnorePatternManager`, `FolderStructureAnalyzer`, etc.).
*   Suscribirse a los cambios del `WorkspaceContext` para actualizar los módulos de contexto cuando los directorios cambien.
*   Inicializar y gestionar el `FileSystemWatcher`, registrando los manejadores de eventos para cada módulo de contexto.
*   Coordinar la construcción del contexto LLM utilizando los datos de los diferentes módulos.
*   Proporcionar una interfaz unificada para acceder a la información del contexto del proyecto.

## 6. Beneficios Esperados

*   **Mayor Modularidad:** El `WorkspaceContext` tendrá una única responsabilidad clara (gestión de directorios).
*   **Menor Cohesión:** Las clases serán más independientes y más fáciles de probar.
*   **Mayor Claridad:** Será más fácil entender cómo se gestionan los directorios y cómo se utiliza esa información para construir el contexto del proyecto.
*   **Mejor Mantenibilidad:** Los cambios en la lógica de análisis de Git, por ejemplo, no requerirán cambios en la clase `WorkspaceContext`.
*   **Escalabilidad:** Facilitará la adición de nuevos módulos de contexto sin sobrecargar el `WorkspaceContext`.

## 7. Plan de Implementación

1.  **Crear una copia de seguridad del archivo actual `workspace_context.py`.**
2.  **Modificar `workspace_context.py`:**
    *   Implementar los cambios propuestos en la sección 4.3.
3.  **Crear la nueva clase `ContextOrchestrator`:**
    *   Implementar las responsabilidades descritas en la sección 5.
4.  **Actualizar las dependencias:** Modificar las partes del código que actualmente interactúan con el `WorkspaceContext` para que interactúen con el `ContextOrchestrator` o el `WorkspaceContext` refactorizado según corresponda.

---
