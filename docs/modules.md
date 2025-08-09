# Módulos del Proyecto KognitoInterpreter

Este documento detalla los módulos principales que componen el proyecto KognitoInterpreter, explicando su propósito, responsabilidades clave y cómo interactúan entre sí.

## 1. `main.py`

*   **Propósito:** Es el punto de entrada principal de la aplicación.
*   **Responsabilidades:**
    *   Parsear los argumentos de línea de comandos (actualmente, la bandera `-y` para el modo de auto-aprobación).
    *   Inicializar y lanzar la interfaz de terminal principal.
*   **Interacciones:** Importa y llama a `start_terminal_interface` desde `gemini_interpreter.terminal.terminal`.

## 2. `gemini_interpreter/terminal/terminal.py`

*   **Propósito:** Gestiona la interfaz de usuario de la línea de comandos (CLI) y el flujo de interacción principal con el usuario.
*   **Responsabilidades:**
    *   Mostrar mensajes de bienvenida y prompts de entrada.
    *   Capturar la entrada del usuario.
    *   Manejar comandos mágicos (`%help`, `%reset`, `%undo`).
    *   Mostrar las respuestas del LLM y la salida de los comandos.
    *   Pedir confirmación al usuario para la ejecución de comandos.
    *   Manejar la cancelación de comandos (`Ctrl+C`).
    *   Integrar mejoras de UI/UX utilizando la librería `rich` (colores, formato Markdown, márgenes).
*   **Interacciones:**
    *   Importa y utiliza la instancia global de `Interpreter` (definida en `bash_agent.py` para la integración con LangGraph).
    *   Invoca el grafo de LangGraph (`bash_agent_app`) para procesar la entrada del usuario.
    *   Utiliza `CommandExecutor` para ejecutar comandos de shell.

## 3. `gemini_interpreter/core/interpreter.py`

*   **Propósito:** Actúa como el puente principal entre la aplicación y el modelo de lenguaje (LLM) de Google Gemini.
*   **Responsabilidades:**
    *   Configurar la API de Gemini utilizando la clave proporcionada por el usuario.
    *   Mantener el historial de la conversación con el LLM.
    *   Enviar mensajes al LLM y recibir sus respuestas.
    *   Extraer comandos de shell de las respuestas del LLM.
    *   Gestionar la adición de mensajes al historial de forma selectiva (para evitar "contaminar" el historial con prompts internos).
*   **Interacciones:**
    *   Depende de la librería `google.generativeai`.
    *   Utiliza `CommandExecutor` para la ejecución real de comandos (aunque la llamada directa se ha movido al grafo de LangGraph, `interpreter` aún tiene una referencia a `executor` y `add_command_output_to_history`).

## 4. `gemini_interpreter/core/command_executor.py`

*   **Propósito:** Ejecutar comandos de shell en un entorno interactivo y capturar su salida.
*   **Responsabilidades:**
    *   Crear y gestionar un pseudo-terminal (PTY) para la ejecución de comandos.
    *   Manejar la comunicación bidireccional con el proceso del comando (enviar entrada del usuario, capturar salida del comando).
    *   Gestionar la configuración de la terminal del usuario (`termios`, `tty`) para permitir la entrada de caracteres en tiempo real (modo `raw`), crucial para contraseñas y prompts interactivos.
    *   Asegurar la limpieza de recursos (descriptores de archivo, procesos) al finalizar o cancelar un comando.
*   **Interacciones:**
    *   Utilizado por `terminal.py` (a través de la instancia de `Interpreter` o directamente en el futuro).
    *   Depende de módulos de bajo nivel como `pty`, `os`, `select`, `subprocess`, `termios`, `tty`.

## 5. `gemini_interpreter/core/agents/bash_agent.py`

*   **Propósito:** Encapsular la lógica de decisión para la interacción con el LLM y la identificación de comandos bash dentro de una estructura de grafo de LangGraph. Es el primer agente especializado del sistema.
*   **Responsabilidades:**
    *   Definir el estado (`AgentState`) que se pasa entre los nodos del grafo.
    *   Definir los nodos del grafo:
        *   `call_model_node`: Llama al LLM y extrae la respuesta y el comando.
        *   `execute_tool_node`: Indica que un comando debe ser ejecutado (la ejecución real ocurre en `terminal.py`).
    *   Definir las transiciones (arcos) entre los nodos, incluyendo lógica condicional.
    *   Compilar el grafo para su ejecución.
*   **Interacciones:**
    *   Importa y utiliza la instancia global de `Interpreter`.
    *   Utilizado por `terminal.py` para invocar el flujo del agente.
    *   Depende de la librería `langgraph`.
