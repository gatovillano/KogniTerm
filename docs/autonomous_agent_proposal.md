# Propuesta de Arquitectura para un Agente Autónomo con Confirmación de Usuario

Esta propuesta detalla cómo refactorizar el `bash_agent` para lograr una mayor autonomía, permitiendo etapas de pensamiento interno y mensajes conversacionales entre llamadas a herramientas, sin detenerse al input de usuario (excepto para confirmaciones explícitas de comandos/código), manteniendo la interactividad de las herramientas.

## 1. Estado del Agente (`AgentState`) - Expansión

Para soportar la autonomía y el pensamiento interno, el `AgentState` necesita ser enriquecido:

```python
@dataclass
class AgentState:
    messages: List[BaseMessage] = field(default_factory=list)
    command_to_confirm: Optional[str] = None # Comando bash que espera confirmación del usuario
    python_code_to_confirm: Optional[str] = None # Código Python que espera confirmación del usuario
    pending_tool_call_id: Optional[str] = None # ID de la llamada a herramienta (execute_command o python_executor) que espera confirmación
    internal_monologue: List[str] = field(default_factory=list) # Pensamientos internos, razonamientos, análisis del agente
    current_goal: Optional[str] = None # Objetivo general de la tarea que el agente está intentando lograr
    current_plan: List[str] = field(default_factory=list) # Pasos detallados del plan actual del agente
    # Otros campos que puedan ser útiles para mantener el contexto de la tarea a largo plazo
```

**Justificación de los nuevos campos:**

*   `python_code_to_confirm`: Para manejar la confirmación específica de código Python.
*   `pending_tool_call_id`: Permite al agente recordar qué llamada a herramienta específica (con sus argumentos originales) estaba esperando confirmación, crucial para reanudar correctamente.
*   `internal_monologue`: Un espacio para que el LLM "piense en voz alta", registre su razonamiento, análisis de resultados y decisiones. Esto mejora la trazabilidad y la calidad de las decisiones autónomas.
*   `current_goal` y `current_plan`: Ayudan al LLM a mantener el rumbo en tareas complejas y de múltiples pasos.

## 2. Nodos del Grafo - Modificaciones y Adiciones

La orquestación se basará en los siguientes nodos, con sus roles y transiciones:

*   **`call_model_node` (Modificado):**
    *   **Función**: Invoca al LLM con el historial completo de mensajes, incluyendo el `internal_monologue`, `current_goal` y `current_plan` en el prompt del sistema o como parte del historial.
    *   **Salida**: El LLM puede generar:
        *   Un `AIMessage` con **solo texto**: Para comunicarse con el usuario, actualizar su monólogo interno, o simplemente "pensar".
        *   Un `AIMessage` con **llamadas a herramientas** (`tool_calls`): Para solicitar la ejecución de `execute_command`, `python_executor`, `file_operations`, etc.
        *   Un `AIMessage` con **ambos**: Texto y llamadas a herramientas (útil para "explica y luego actúa" o para dar contexto a una herramienta).
    *   **Transiciones**:
        *   A `explain_and_pause_for_confirm_node` si se detecta `execute_command` o `python_executor`.
        *   A `execute_other_tools_node` si se detectan otras herramientas.
        *   A `reflect_node` si solo hay texto o si el LLM necesita analizar el estado sin una acción directa.
        *   A `finish_task_node` si el LLM indica que la tarea está completa.

*   **`explain_and_pause_for_confirm_node` (Nuevo/Modificado):**
    *   **Activación**: Cuando `call_model_node` genera un `tool_call` para `execute_command` o `python_executor`.
    *   **Acción**:
        1.  Extrae el comando/código y sus argumentos de la `tool_call`.
        2.  Genera una explicación en lenguaje natural de lo que hará el comando/código.
        3.  Añade esta explicación al historial de mensajes (`AIMessage`).
        4.  Establece `command_to_confirm` (o `python_code_to_confirm`) y `pending_tool_call_id` en el `AgentState`.
        5.  **PAUSA LA EJECUCIÓN DEL GRAFO**. El control se devuelve a la interfaz de `kogniterm` para que pida confirmación al usuario.
    *   **Transición**: A `confirm_await_state` (un estado conceptual que representa la espera de input externo).

*   **`resume_after_confirm_node` (Nuevo):**
    *   **Activación**: Este nodo se activa **externamente** por la interfaz de `kogniterm` una vez que el usuario ha proporcionado la confirmación (Sí/No) para un comando o código Python.
    *   **Acción**:
        1.  Lee la respuesta del usuario (inyectada en el estado o como un mensaje especial).
        2.  Si el usuario **confirma**:
            *   Ejecuta la herramienta original (`execute_command` o `python_executor`) usando los argumentos guardados en `pending_tool_call_id`.
            *   Añade la salida de la herramienta como `ToolMessage` al historial.
        3.  Si el usuario **deniega**:
            *   Añade un `ToolMessage` indicando que la ejecución fue denegada por el usuario.
        4.  Limpia `command_to_confirm`, `python_code_to_confirm` y `pending_tool_call_id` del `AgentState`.
    *   **Transición**: A `reflect_node`.

*   **`execute_other_tools_node` (Modificado `execute_tool_node`):**
    *   **Función**: Ejecuta cualquier herramienta solicitada por el LLM **excepto** `execute_command` o `python_executor` cuando estos requieren confirmación (es decir, cuando el flujo pasa por `explain_and_pause_for_confirm_node`).
    *   **Acción**: Invoca la herramienta y añade su salida como `ToolMessage` al historial.
    *   **Transición**: A `reflect_node`.

*   **`reflect_node` (Nuevo - Pensamiento Interno):**
    *   **Función**: Permite al LLM analizar el estado actual, la salida de la última acción y planificar el siguiente paso.
    *   **Activación**: Se activa después de `execute_other_tools_node`, `resume_after_confirm_node`, o directamente desde `call_model_node` si el LLM necesita solo pensar o generar un mensaje.
    *   **Acción**: El LLM recibe un prompt que incluye el historial de mensajes, su `internal_monologue`, `current_goal` y `current_plan`. Su tarea es:
        *   Analizar la salida de la última acción o el estado general.
        *   Actualizar su `internal_monologue`, `current_goal` y `current_plan` (posiblemente generando un `AIMessage` de texto con estos pensamientos).
        *   Decidir el siguiente paso:
            *   ¿La tarea está completa? (Transicionar a `finish_task_node`).
            *   ¿Necesito otra herramienta? (Transicionar a `call_model_node`).
            *   ¿Necesito generar un mensaje conversacional al usuario antes de la siguiente acción? (Generar un `AIMessage` con `content` y luego transicionar a `call_model_node` o `reflect_node`).
            *   ¿Necesito pedir más información al usuario (no una confirmación de comando)? (Transicionar a `ask_user_node`).
    *   **Transiciones**: A `call_model_node`, `finish_task_node`, o `ask_user_node`.

*   **`finish_task_node` (Nuevo):**
    *   **Función**: Marca el final de la tarea del agente.
    *   **Activación**: Cuando el LLM en `reflect_node` (o `call_model_node`) determina que la tarea está completa.
    *   **Acción**: Añade un mensaje final al usuario.
    *   **Transición**: A `END`.

*   **`ask_user_node` (Opcional - Nuevo):**
    *   **Función**: Permite al agente solicitar información adicional al usuario que no es una confirmación de comando/código.
    *   **Activación**: Cuando el LLM en `reflect_node` (o `call_model_node`) necesita una entrada específica del usuario.
    *   **Acción**: Genera un mensaje claro para el usuario. **PAUSA LA EJECUCIÓN DEL GRAFO**.
    *   **Transición**: A `user_input_await_state` (estado conceptual). La interfaz de `kogniterm` reanudaría el grafo, inyectando la respuesta del usuario, y el flujo volvería a `call_model_node`.

## 3. Flujo del Grafo (LangGraph)

```mermaid
graph TD
    A[START: User Request] --> B(call_model_node)

    B -->|Tool Call (execute_command or python_executor)| D{explain_and_pause_for_confirm_node}
    B -->|Tool Call (other tools)| C(execute_other_tools_node)
    B -->|Only Text / Need to Reflect| E(reflect_node)
    B -->|Task Completed| F(finish_task_node)

    C --> E

    D -- PAUSE --> G(kogniterm CLI / External Handler)
    G -->|User Confirms / Denies| H(resume_after_confirm_node)

    H --> E

    E -->|Next Tool Call| B
    E -->|Only Text / Need to Reflect More| B
    E -->|Task Completed| F
    E -->|Need User Input (not command/code confirm)| I(ask_user_node)

    I -- PAUSE --> G_INPUT(kogniterm CLI / External Handler for Input)
    G_INPUT -->|User Provides Input| B

    F --> J[END]
```

## 4. Gestión de Pausas y Reanudaciones en `kogniterm` CLI

La clave para que el agente "intercale" mensajes y acciones sin "volver al input de usuario" (excepto para confirmaciones) reside en cómo el bucle principal de `kogniterm` gestiona el grafo:

1.  **Bucle de Ejecución**: El bucle principal de `kogniterm` llamará a `bash_agent_graph.invoke(state)` repetidamente.
2.  **Detección de Pausa**: Después de cada `invoke`, el controlador examinará el `AgentState` resultante:
    *   Si `state.command_to_confirm` o `state.python_code_to_confirm` están establecidos, el controlador:
        *   Imprimirá el `AIMessage` de explicación generado por `explain_and_pause_for_confirm_node`.
        *   Pedirá la confirmación al usuario.
        *   Una vez que el usuario responda, el controlador construirá un nuevo `HumanMessage` (o un flag especial en el estado) con la respuesta y llamará a `bash_agent_graph.invoke()` nuevamente, dirigiendo el flujo al `resume_after_confirm_node`.
    *   Si el agente transiciona a `ask_user_node`, el controlador imprimirá el mensaje del agente y esperará la entrada del usuario, luego la inyectará de vuelta al grafo.
3.  **Flujo Continuo Interno**: Si no hay una confirmación o una solicitud de input del usuario pendiente, el controlador simplemente seguirá invocando el grafo, permitiendo que el agente pase por `call_model_node`, `execute_other_tools_node`, `reflect_node` y genere mensajes conversacionales o realice acciones sin interrupción externa.

Esta arquitectura permite un agente más autónomo que puede razonar, planificar y ejecutar múltiples pasos, intercalando explicaciones y acciones, mientras mantiene la capa de seguridad crítica de la confirmación del usuario para operaciones potencialmente destructivas.
