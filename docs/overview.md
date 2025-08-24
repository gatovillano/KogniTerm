# Visión General del Proyecto KogniTerm

## Propósito

**KogniTerm** es un intérprete de línea de comandos interactivo diseñado para permitir que los modelos de lenguaje (LLMs) interactúen directamente con el sistema operativo del usuario. Su objetivo principal es proporcionar una interfaz conversacional y asistida para la ejecución de comandos y la orquestación de tareas complejas a través del lenguaje natural.

Este proyecto busca ofrecer una integración robusta y funcional con modelos de Google Gemini, superando las limitaciones de compatibilidad de otras herramientas.

## Arquitectura General

La arquitectura de KogniTerm se basa en un diseño modular y en el uso de **LangGraph** para la gestión del flujo de los agentes:

1.  **Interfaz de Terminal (`terminal.py`):** Actúa como el punto de entrada y salida para el usuario. Maneja la entrada de comandos, la visualización de las respuestas del LLM y la salida de los comandos ejecutados. Incorpora mejoras de UI/UX con la librería `rich` y permite alternar entre diferentes modos de agente.

2.  **Servicio LLM (`llm_service.py`):** Es el componente central para la interacción con el modelo de lenguaje (LLM) de Google Gemini. Se encarga de configurar la API, convertir las herramientas al formato de Gemini e invocar el modelo. También provee un método para buscar herramientas por nombre.

3.  **Ejecutor de Comandos (`command_executor.py`):** Responsable de ejecutar comandos de shell en el sistema. Está diseñado para manejar sesiones interactivas (usando pseudo-terminales), permitiendo la entrada de usuario (como contraseñas o confirmaciones `[Y/n]`) y la captura de salida en tiempo real.

4.  **Agentes LangGraph (`core/agents/`):** Son el cerebro de la aplicación, implementados como grafos de LangGraph. Deciden qué acciones tomar, cómo usar las herramientas y cómo interactuar con el usuario. Actualmente, existen dos modos principales:
    *   **Agente Bash (`bash_agent.py`):** Para la ejecución directa de comandos y herramientas, proporcionando explicaciones claras antes de la confirmación.
    *   **Agente Orquestador (`orchestrator_agent.py`):** Para tareas complejas que requieren planificación, aprobación del usuario y ejecución secuencial de múltiples pasos.

## Flujo de Interacción Básico

1.  El usuario introduce una consulta en la terminal.
2.  La interfaz de terminal (`terminal.py`) añade la consulta al historial del agente activo (Bash o Orquestador).
3.  El agente activo (`bash_agent.py` o `orchestrator_agent.py`) invoca al Servicio LLM (`llm_service.py`) con el historial de la conversación.
4.  El LLM genera una respuesta que puede ser texto conversacional o una llamada a una herramienta.
5.  Si el LLM propone ejecutar un comando (`execute_command`):
    *   El agente genera una explicación en lenguaje natural sobre lo que hará el comando.
    *   La terminal (`terminal.py`) intercepta esta propuesta, muestra la explicación y pide confirmación al usuario.
    *   Si el usuario aprueba (o si el modo de auto-aprobación está activo), la terminal utiliza el `command_executor.py` para ejecutar el comando.
    *   La salida del comando se captura y se envía de vuelta al agente como una respuesta de herramienta.
6.  Si el LLM propone usar otra herramienta (ej. `github_tool`, `brave_search`):
    *   El agente ejecuta la herramienta directamente (sin confirmación adicional, ya que no modifican el sistema de archivos directamente).
    *   La salida de la herramienta se envía de vuelta al agente.
7.  El agente procesa la salida de la herramienta o el comando, y genera una respuesta conversacional para el usuario.
8.  La respuesta final del agente se muestra en la terminal.

En el modo Orquestador, este flujo se extiende para incluir la generación de un plan de múltiples pasos, su presentación al usuario para aprobación, y la ejecución secuencial de cada paso del plan.