# Módulos del Proyecto KogniTerm

Este documento detalla los módulos principales que componen el proyecto KogniTerm, explicando su propósito, responsabilidades clave y cómo interactúan entre sí.

## 1. `main.py`

*   **Propósito:** Es el punto de entrada principal de la aplicación.
*   **Responsabilidades:**
    *   Parsear los argumentos de línea de comandos (actualmente, la bandera `-y` para el modo de auto-aprobación).
    *   Inicializar y lanzar la interfaz de terminal principal.
*   **Interacciones:** Importa y llama a `start_terminal_interface` desde `kogniterm.terminal.terminal`.

## 2. `kogniterm/terminal/terminal.py`

*   **Propósito:** Gestiona la interfaz de usuario de la línea de comandos (CLI) y el flujo de interacción principal con el usuario.
*   **Responsabilidades:**
    *   Mostrar mensajes de bienvenida y prompts de entrada.
    *   Capturar la entrada del usuario.
    *   Manejar comandos mágicos (`%help`, `%reset`, `%undo`, `%agentmode`).
    *   Mostrar las respuestas del LLM y la salida de los comandos.
    *   Pedir confirmación al usuario para la ejecución de comandos y ejecutarlos directamente.
    *   Manejar la cancelación de comandos (`Ctrl+C`).
    *   Integrar mejoras de UI/UX utilizando la librería `rich` (colores, formato Markdown, márgenes).
    *   Alternar entre `bash_agent_app` y `orchestrator_app`.
*   **Interacciones:**
    *   Utiliza una instancia global de `CommandExecutor` para ejecutar comandos de shell.
    *   Invoca los grafos de LangGraph (`bash_agent_app` y `orchestrator_app`) para procesar la entrada del usuario.

## 3. `kogniterm/core/llm_service.py`

*   **Propósito:** Centraliza la interacción con el modelo de lenguaje (LLM) de Google Gemini y la gestión de herramientas.
*   **Responsabilidades:**
    *   Configurar la API de Gemini.
    *   Convertir herramientas de LangChain a un formato compatible con Gemini.
    *   Invocar el modelo Gemini con el historial de conversación y herramientas.
    *   Proveer un método para buscar herramientas por nombre.
*   **Interacciones:**
    *   Utilizado por los agentes (`bash_agent.py` y `orchestrator_agent.py`).
    *   Depende de la librería `google.generativeai` y `langchain_core.tools`.

## 4. `kogniterm/core/command_executor.py`

*   **Propósito:** Ejecutar comandos de shell en un entorno interactivo y capturar su salida.
*   **Responsabilidades:**
    *   Crear y gestionar un pseudo-terminal (PTY) para la ejecución de comandos.
    *   Manejar la comunicación bidireccional con el proceso del comando.
    *   Gestionar la configuración de la terminal del usuario para interactividad.
    *   Asegurar la limpieza de recursos.
*   **Interacciones:**
    *   Utilizado directamente por `terminal.py` para la ejecución de comandos confirmados.
    *   Utilizado por la herramienta `execute_command` (aunque la ejecución final la maneja `terminal.py`).

## 5. `kogniterm/core/agents/bash_agent.py`

*   **Propósito:** Encapsular la lógica de decisión para la interacción con el LLM y la ejecución de comandos/herramientas dentro de una estructura de grafo de LangGraph. Es el agente para interacciones directas.
*   **Responsabilidades:**
    *   Definir el estado (`AgentState`) que incluye el historial de mensajes y un campo para comandos a confirmar (`command_to_confirm`).
    *   Definir nodos del grafo:
        *   `call_model_node`: Llama al LLM y procesa su respuesta (texto o llamadas a herramientas).
        *   `explain_command_node`: Genera una explicación en lenguaje natural del comando propuesto.
        *   `execute_tool_node`: Señaliza a `terminal.py` para confirmar `execute_command`, o ejecuta otras herramientas directamente.
        *   `confirm_command` (nodo passthrough): Señaliza que un comando está listo para confirmación.
    *   Definir transiciones condicionales para el flujo del agente.
*   **Interacciones:**
    *   Utiliza `LLMService` para comunicarse con el LLM.
    *   Utilizado por `terminal.py` para invocar el flujo del agente.
    *   Comparte `AgentState`, `call_model_node`, `execute_tool_node`, `should_continue` con `orchestrator_agent.py`.

## 6. `kogniterm/core/agents/orchestrator_agent.py`

*   **Propósito:** Orquestar tareas complejas de múltiples pasos, incluyendo planificación, presentación al usuario y ejecución secuencial.
*   **Responsabilidades:**
    *   Reutiliza `AgentState` y los nodos principales (`call_model_node`, `execute_tool_node`, `explain_command_node`, `confirm_command`) de `bash_agent.py`.
    *   Define un `SYSTEM_MESSAGE` específico para la orquestación.
    *   Implementa nodos adicionales para:
        *   `create_plan_node`: Genera un plan detallado para la tarea.
        *   `present_plan_node`: Formatea y presenta el plan al usuario para aprobación.
        *   `handle_approval_node`: Procesa la respuesta de aprobación del usuario.
        *   `execute_task_node`: Ejecuta un paso del plan (señalizando a `terminal.py` o ejecutando herramientas).
        *   `handle_output_node`: Evalúa la salida de un paso y decide el siguiente.
*   **Interacciones:**
    *   Utiliza `LLMService` para comunicarse con el LLM.
    *   Utilizado por `terminal.py` para invocar el flujo del agente.