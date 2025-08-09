# Visión General del Proyecto KognitoInterpreter

## Propósito

**KognitoInterpreter** es un intérprete de línea de comandos interactivo diseñado para permitir que los modelos de lenguaje (LLMs) interactúen directamente con el sistema operativo del usuario. Su objetivo principal es proporcionar una interfaz conversacional y asistida para la ejecución de comandos, haciendo que las tareas complejas sean más accesibles y automatizables a través del lenguaje natural.

Este proyecto nace como una alternativa a otras implementaciones, buscando una integración más robusta y funcional con modelos de Google Gemini, abordando las limitaciones de compatibilidad que pueden presentarse en otras herramientas.

## Arquitectura General

La arquitectura de KognitoInterpreter se basa en un diseño modular que separa las responsabilidades clave:

1.  **Interfaz de Terminal (`terminal.py`):** Actúa como el punto de entrada y salida para el usuario. Maneja la entrada de comandos del usuario, la visualización de las respuestas del LLM y la salida de los comandos ejecutados. Incorpora mejoras de UI/UX con la librería `rich`.

2.  **Núcleo del Intérprete (`interpreter.py`):** Es el cerebro que interactúa directamente con el modelo de lenguaje (LLM). Gestiona la comunicación con la API de Gemini, mantiene el historial de la conversación y extrae comandos de las respuestas del LLM.

3.  **Ejecutor de Comandos (`command_executor.py`):** Responsable de ejecutar comandos de shell en el sistema. Está diseñado para manejar sesiones interactivas, permitiendo la entrada de usuario (como contraseñas o confirmaciones `[Y/n]`) y la captura de salida en tiempo real.

4.  **Agentes LangGraph (`core/agents/`):** Representa la futura evolución del proyecto hacia una arquitectura basada en agentes. Actualmente, el `bash_agent.py` encapsula la lógica de decisión para la ejecución de comandos bash, sentando las bases para un orquestador más complejo.

## Flujo de Interacción Básico

1.  El usuario introduce una consulta en la terminal.
2.  La interfaz de terminal (`terminal.py`) envía esta consulta al núcleo del intérprete.
3.  El núcleo del intérprete (`interpreter.py`) interactúa con el LLM (Gemini).
4.  El LLM genera una respuesta que puede contener texto conversacional y/o un comando de shell.
5.  La interfaz de terminal muestra la respuesta conversacional del LLM.
6.  Si se detecta un comando, la interfaz pide confirmación al usuario (a menos que esté en modo auto-aprobación).
7.  Si se aprueba, el ejecutor de comandos (`command_executor.py`) ejecuta el comando, gestionando la interactividad si es necesario.
8.  La salida del comando es capturada y enviada de vuelta al LLM para generar una respuesta conversacional sobre el resultado.
9.  La respuesta final se muestra al usuario.

## Próximos Pasos (Roadmap)

El siguiente gran paso es la implementación completa de la **Fase 2: El Orquestador y la Planificación** utilizando LangGraph. Esto transformará el sistema en un agente capaz de:

*   Crear planes de múltiples pasos para tareas complejas.
*   Presentar planes al usuario para su aprobación.
*   Delegar tareas a agentes especializados (como el Agente Bash, Agente de Búsqueda Web, Agente de Archivos, etc.).
*   Evaluar los resultados y adaptar el plan dinámicamente.
