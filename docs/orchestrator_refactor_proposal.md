# Propuesta de Refactorización Detallada para el Agente Orquestador en KogniTerm

Basándome en el análisis del proyecto KogniTerm, propongo una refactorización del agente orquestador para hacerlo más autónomo, robusto y modular. El objetivo es que el orquestador maneje su propio flujo de planificación, presentación y ejecución de tareas, minimizando la lógica de control en `terminal.py`.

---

### **Objetivo Principal:**

Hacer que el agente orquestador sea completamente responsable de:
1.  Generar un plan estructurado para la solicitud del usuario.
2.  Presentar ese plan al usuario para aprobación.
3.  Procesar la decisión de aprobación del usuario.
4.  Ejecutar secuencialmente cada paso del plan, distinguiendo entre comandos `execute_command` y otras herramientas.
5.  Evaluar la salida de cada paso y decidir el siguiente.
6.  Generar una respuesta final al usuario una vez completado el plan.

Esto implica mover gran parte de la lógica de "manejo de plan" que actualmente reside en `terminal.py` al grafo del `orchestrator_agent.py`.

---

### **1. Definir un `OrchestratorState` más Robusto (en `kogniterm/core/agents/orchestrator_agent.py`)**

Reutilizaremos `AgentState` del `bash_agent.py` como base, pero añadiremos campos específicos para el flujo del orquestador.

```python
# kogniterm/core/agents/orchestrator_agent.py

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import json # Necesario para parsear el plan JSON
import re   # Para expresiones regulares

# Reutilizar AgentState del bash_agent para la base de mensajes
from .bash_agent import AgentState as BaseAgentState
from ..llm_service import llm_service # Asegúrate de que llm_service esté disponible

# --- Mensaje de Sistema para el Orquestador (Ajustado) ---
# Este mensaje debe guiar al LLM para generar un plan estructurado
SYSTEM_MESSAGE = SystemMessage(content=\"\"\"Eres un agente orquestador experto.
Tu objetivo es desglosar problemas complejos en una secuencia de pasos ejecutables y llevarlos a cabo usando tus herramientas.
Antes de cualquier acción, crea un plan detallado paso a paso para abordar la solicitud del usuario.

1.  **Analiza la Petición**: Comprende la solicitud completa del usuario.
2.  **Crea un Plan ESTRUCTURADO**: Genera un plan de acción detallado y paso a paso para resolver la solicitud.
    Tu respuesta DEBE ser un objeto JSON que contenga una clave 'plan' con una lista de diccionarios, cada uno con 'description' y 'action'.
    - 'description': Explicación en lenguaje natural del paso.
    - 'action': El comando bash o la llamada a la herramienta a ejecutar.

    Si la acción es un comando bash, debe estar en formato `execute_command(command='tu_comando_aqui')`.
    Si la acción es una llamada a una herramienta (ej. brave_search, github_tool), debe estar en formato `nombre_herramienta(param1='valor1', param2='valor2')`.
    Asegúrate de que el plan sea exhaustivo y cubra todos los aspectos de la solicitud.

    Ejemplo de formato de respuesta:
    ```json
    {
        "plan": [
            {
                "description": "Buscar información sobre el tema X en la web.",
                "action": "brave_search(query='informacion sobre X')"
            },
            {
                "description": "Listar los archivos en el directorio actual.",
                "action": "execute_command(command='ls -la')"
            }
        ]
    }
    ```
3.  **Piensa Paso a Paso**: Decide cuál es la primera acción que debes tomar basándote en el plan. No intentes resolver todo de una vez.
4.  **Ejecuta una Acción**: Usa una de tus herramientas para realizar el primer paso. La herramienta más común que usarás es `execute_command` para correr comandos de terminal.
5.  **Observa el Resultado**: Después de cada ejecución de herramienta, recibirás el resultado. Analízalo.
6.  **Decide el Siguiente Paso**: Basado en el resultado y el plan, decide si la tarea está completa o cuál es la siguiente acción a tomar.
7.  **Repite**: Continúa este ciclo de acción y observación hasta que la solicitud del usuario esté completamente resuelta.
8.  **Responde al Usuario**: Solo cuando la tarea esté 100% completada, proporciona una respuesta final y amigable al usuario.

Cuando recibas la salida de una herramienta, analízala, resúmela y preséntala al usuario de forma clara y amigable, utilizando formato Markdown si es apropiado.
\"\"\")

@dataclass
class OrchestratorState(BaseAgentState):
    \"\"\"Define la estructura del estado que fluye a través del grafo del orquestador.\"\"\"
    # Hereda 'messages' de BaseAgentState

    user_query: str = "" # La consulta inicial del usuario que desencadena el plan
    plan: List[Dict[str, Any]] = field(default_factory=list) # Lista de pasos del plan (description, action)
    plan_presentation: str = "" # La versión formateada del plan para mostrar al usuario
    current_task_index: int = 0 # Índice de la tarea actual en el plan
    user_approval: Optional[bool] = None # True/False/None para aprobación del plan

    # Estos campos se usarán para comunicar al terminal qué acción se necesita
    command_to_execute: Optional[str] = None # El comando bash a ejecutar (si es una acción de execute_command)
    action_needed: Optional[str] = None # "await_user_approval", "execute_command", "final_response"

    final_response: str = "" # La respuesta final del orquestador al usuario
    status: str = "planning" # planning, presenting_plan, executing_task, finished, failed
```

---

### **2. Nodos del Grafo del Orquestador (en `kogniterm/core/agents/orchestrator_agent.py`)**

#### **2.1. `create_plan_node` (Generación del Plan)**

Este nodo es crucial. Deberá generar el plan en un formato JSON estructurado y parsearlo para almacenarlo en `state.plan`.

```python
# kogniterm/core/agents/orchestrator_agent.py

# ... (importaciones y OrchestratorState) ...

async def create_plan_node(state: OrchestratorState):
    \"\"\"
    Genera un plan de acción detallado y estructurado utilizando el LLM en formato JSON.
    \"\"\"
    # El SYSTEM_MESSAGE ya contiene las instrucciones para el formato JSON.
    # El LLM debe responder con el JSON.

    # Asegúrate de que el historial solo contenga el mensaje del sistema y la consulta del usuario
    # para que el LLM se centre en la planificación.
    # El user_query se añade al estado en terminal.py antes de invocar por primera vez.
    temp_history = [SYSTEM_MESSAGE, HumanMessage(content=state.user_query)]

    response = llm_service.invoke(history=temp_history)

    ai_message_content = ""
    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.text:
                ai_message_content += part.text
            # Ignoramos tool_calls aquí; esperamos un JSON de plan.

    # Extraer y parsear el JSON del plan
    plan_json = None
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", ai_message_content, re.DOTALL)
    if json_match:
        try:
            plan_json = json.loads(json_match.group(1))
            state.plan = plan_json.get("plan", [])
            state.status = "presenting_plan" # Transicionar al estado de presentación
            state.action_needed = "await_user_approval" # Necesitamos la aprobación del usuario
            state.messages.append(AIMessage(content="Plan generado exitosamente.")) # Añadir un mensaje simple
        except json.JSONDecodeError as e:
            state.final_response = f"Error al parsear el plan JSON: {e}. Respuesta del modelo: {ai_message_content}"
            state.status = "failed"
            state.action_needed = "final_response"
            state.messages.append(AIMessage(content=state.final_response))
    else:
        state.final_response = f"El modelo no generó un plan en formato JSON. Respuesta: {ai_message_content}"
        state.status = "failed"
        state.action_needed = "final_response"
        state.messages.append(AIMessage(content=state.final_response))

    return state
```

#### **2.2. `present_plan_node` (Presentación del Plan)**

Formatea el plan para mostrarlo al usuario.

```python
# kogniterm/core/agents/orchestrator_agent.py

def present_plan_node(state: OrchestratorState):
    \"\"\"
    Formatea el plan para presentarlo al usuario y establece la acción necesaria para la aprobación.
    \"\"\"
    if not state.plan:
        state.final_response = "El plan está vacío. No hay acciones que realizar."
        state.status = "failed"
        state.action_needed = "final_response"
        state.messages.append(AIMessage(content=state.final_response))
        return state

    formatted_plan = "### Plan de Acción Propuesto:\n"
    for i, step in enumerate(state.plan):
        formatted_plan += f"{i+1}. **{step.get('description', 'Sin descripción')}**\n"
        action = step.get('action', 'N/A')
        formatted_plan += f"   `{action}`\n"

    formatted_plan += "\nPor favor, revisa el plan. ¿Deseas aprobarlo y comenzar la ejecución? (s/n)"

    state.plan_presentation = formatted_plan
    state.status = "presenting_plan"
    state.action_needed = "await_user_approval" # Señal para terminal.py

    state.messages.append(AIMessage(content=formatted_plan)) # Añadir al historial
    return state
```

#### **2.3. `handle_approval_node` (Manejo de Aprobación)**

Procesa la respuesta del usuario (recibida de `terminal.py`).

```python
# kogniterm/core/agents/orchestrator_agent.py

def handle_approval_node(state: OrchestratorState):
    \"\"\"
    Procesa la aprobación o denegación del plan por parte del usuario.
    \"\"\"
    # user_approval se establecerá en terminal.py antes de re-invocar el grafo
    if state.user_approval is True:
        state.status = "executing_task"
        state.current_task_index = 0 # Iniciar desde la primera tarea
        state.action_needed = "execute_task" # Señal para ejecutar la primera tarea
        state.messages.append(AIMessage(content="Plan aprobado. Iniciando ejecución..."))
    else: # user_approval is False o None (si se canceló)
        state.final_response = "Plan no aprobado. La ejecución ha sido cancelada."
        state.status = "failed" # O "cancelled" si quieres un estado más específico
        state.action_needed = "final_response"
        state.messages.append(AIMessage(content=state.final_response))
    return state
```

#### **2.4. `execute_task_node` (Ejecución de Tareas)**

Este nodo es el corazón de la ejecución. Debe analizar la `action` del paso actual y ejecutarla.

```python
# kogniterm/core/agents/orchestrator_agent.py

def execute_task_node(state: OrchestratorState):
    \"\"\"
    Ejecuta la tarea actual del plan.
    Debe manejar tanto comandos bash (señalizando a terminal.py) como llamadas a otras herramientas (ejecutando directamente).
    \"\"\"
    if state.current_task_index >= len(state.plan):
        state.final_response = "Error: Intentando ejecutar una tarea fuera de los límites del plan."
        state.status = "failed"
        state.action_needed = "final_response"
        state.messages.append(AIMessage(content=state.final_response))
        return state

    current_task = state.plan[state.current_task_index]
    action_str = current_task.get("action", "")

    state.messages.append(AIMessage(content=f"Ejecutando paso {state.current_task_index + 1}: {current_task.get('description', 'N/A')}"))

    # Regex para extraer el nombre de la herramienta y los argumentos
    # Esto es un parser simple; para mayor robustez, se podría usar ast.literal_eval o un parser más avanzado.
    tool_call_match = re.match(r"(\w+)\((.*)\)", action_str)

    if tool_call_match:
        tool_name = tool_call_match.group(1)
        args_str = tool_call_match.group(2)

        tool_args = {}
        try:
            # Intentar parsear los argumentos de una manera más flexible
            # Asegurarse de que las cadenas estén entre comillas dobles para json.loads
            # Reemplazar comillas simples por dobles si es necesario para compatibilidad JSON
            args_str_json_compatible = args_str.replace("'", "\"")
            # Envolver en un objeto JSON para facilitar el parseo
            tool_args = json.loads(f"{{{args_str_json_compatible}}}")
        except json.JSONDecodeError:
            # Fallback a un parser más simple si el JSON falla (ej. key=value)
            try:
                for arg_pair in args_str.split(','):
                    if '=' in arg_pair:
                        key, value = arg_pair.split('=', 1)
                        tool_args[key.strip()] = value.strip().strip("'\"") # Eliminar comillas
            except Exception as e:
                state.final_response = f"Error al parsear argumentos de la herramienta en '{action_str}': {e}"
                state.status = "failed"
                state.action_needed = "final_response"
                state.messages.append(AIMessage(content=state.final_response))
                return state

        if tool_name == "execute_command":
            command = tool_args.get("command")
            if command:
                state.command_to_execute = command
                state.action_needed = "execute_command" # Señal para terminal.py
                # La salida de este comando será manejada por terminal.py y re-invocará al orquestador.
            else:
                state.final_response = "Error: 'execute_command' requiere un parámetro 'command'."
                state.status = "failed"
                state.action_needed = "final_response"
                state.messages.append(AIMessage(content=state.final_response))
        else:
            # Es una llamada a otra herramienta (ej. brave_search, github_tool)
            tool = llm_service.get_tool(tool_name)
            if tool:
                try:
                    tool_output = tool.invoke(tool_args)
                    # Añadir la salida de la herramienta directamente al historial de mensajes
                    state.messages.append(ToolMessage(content=str(tool_output), tool_call_id=tool_name))
                    state.action_needed = "handle_output" # Procesar la salida
                    state.status = "executing_task" # Sigue en ejecución hasta que se evalúe la salida
                except Exception as e:
                    state.final_response = f"Error al ejecutar la herramienta '{tool_name}': {e}"
                    state.status = "failed"
                    state.action_needed = "final_response"
                    state.messages.append(AIMessage(content=state.final_response))
            else:
                state.final_response = f"Error: Herramienta '{tool_name}' no encontrada."
                state.status = "failed"
                state.action_needed = "final_response"
                state.messages.append(AIMessage(content=state.final_response))
    else:
        state.final_response = f"Error: Formato de acción no reconocido en el plan: '{action_str}'"
        state.status = "failed"
        state.action_needed = "final_response"
        state.messages.append(AIMessage(content=state.final_response))

    return state
```

#### **2.5. `handle_output_node` (Manejo de Salida y Decisión)**

Evalúa el resultado de la última acción y decide si avanzar, finalizar o fallar.

```python
# kogniterm/core/agents/orchestrator_agent.py

def handle_output_node(state: OrchestratorState):
    \"\"\"
    Evalúa la salida de la última tarea ejecutada y decide el siguiente paso.
    \"\"\"
    # En este punto, la salida del comando o herramienta ya ha sido añadida a state.messages
    # por terminal.py (para execute_command) o por execute_task_node (para otras herramientas).

    # Podemos usar el LLM para evaluar la salida si es compleja, pero para empezar,
    # simplemente avanzamos si no hubo un error explícito.

    # Comprobar el último mensaje para ver si fue un error
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and "Error" in last_message.content:
        state.final_response = f"La tarea {state.current_task_index + 1} falló: {last_message.content}"
        state.status = "failed"
        state.action_needed = "final_response"
        return state
    elif isinstance(last_message, ToolMessage) and "Error" in last_message.content:
        state.final_response = f"La tarea {state.current_task_index + 1} falló con salida de herramienta: {last_message.content}"
        state.status = "failed"
        state.action_needed = "final_response"
        return state

    state.current_task_index += 1

    if state.current_task_index < len(state.plan):
        state.status = "executing_task"
        state.action_needed = "execute_task" # Hay más tareas
        state.messages.append(AIMessage(content=f"Tarea {state.current_task_index} completada. Pasando a la siguiente."))
    else:
        state.final_response = "Todas las tareas del plan han sido completadas con éxito."
        state.status = "finished"
        state.action_needed = "final_response"
        state.messages.append(AIMessage(content=state.final_response))

    return state
```

---

### **3. Construcción del Grafo del Orquestador (en `kogniterm/core/agents/orchestrator_agent.py`)**

Ahora, conectemos los nodos para definir el flujo.

```python
# kogniterm/core/agents/orchestrator_agent.py

# ... (definiciones de nodos y estado) ...

# --- Construcción del Grafo del Orquestador ---

orchestrator_graph = StateGraph(OrchestratorState)

# Añadimos los nodos
orchestrator_graph.add_node("create_plan", create_plan_node)
orchestrator_graph.add_node("present_plan", present_plan_node)
orchestrator_graph.add_node("handle_approval", handle_approval_node)
orchestrator_graph.add_node("execute_task", execute_task_node)
orchestrator_graph.add_node("handle_output", handle_output_node)

# Punto de entrada: siempre comienza creando el plan
orchestrator_graph.set_entry_point("create_plan")

# Transiciones

# 1. Después de crear el plan, se presenta para aprobación
orchestrator_graph.add_edge("create_plan", "present_plan")

# 2. Después de presentar el plan, la terminal espera la aprobación del usuario
# y re-invoca el grafo, lo que nos lleva a 'handle_approval'.
# No hay una arista directa desde 'present_plan' porque la interacción es externa.

# 3. Después de manejar la aprobación, decidimos si ejecutar la primera tarea o finalizar
orchestrator_graph.add_conditional_edges(
    "handle_approval",
    lambda state: "execute_task" if state.user_approval else END,
    {
        "execute_task": "execute_task",
        END: END # El plan no fue aprobado
    }
)

# 4. Después de ejecutar una tarea (ya sea un comando o una herramienta directa),
# se maneja su salida.
# Nota: Si execute_task_node establece action_needed = "execute_command",
# la terminal ejecutará el comando y luego re-invocará el grafo, llevando
# al estado a 'handle_output' para procesar la salida del comando.
orchestrator_graph.add_edge("execute_task", "handle_output")

# 5. Después de manejar la salida, se decide si continuar con la siguiente tarea o finalizar.
orchestrator_graph.add_conditional_edges(
    "handle_output",
    lambda state: "execute_task" if state.current_task_index < len(state.plan) else END,
    {
        "execute_task": "execute_task", # Continuar con la siguiente tarea
        END: END # Todas las tareas completadas
    }
)

# Compilamos el grafo para el orquestador
orchestrator_app = orchestrator_graph.compile()
```

---

### **4. Sincronización con `terminal.py`**

`terminal.py` necesitará ser el "puente" entre el usuario y el grafo del orquestador, gestionando las pausas para aprobación y la ejecución interactiva de comandos.

**Cambios clave en `kogniterm/terminal/terminal.py`:**

```python
# kogniterm/terminal/terminal.py (Fragmento de la función start_terminal_interface)

import sys
import os
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from ..core.command_executor import CommandExecutor

# ... (Rich imports y print_welcome_banner) ...

# Importaciones de Agentes (asegúrate de que OrchestratorState también se importe)
from ..core.agents.bash_agent import bash_agent_app, AgentState
from ..core.agents.orchestrator_agent import orchestrator_app, OrchestratorState # <-- Importar OrchestratorState

# ... (Estado Global de la Terminal) ...

def start_terminal_interface(auto_approve=False):
    # ... (inicialización y banner) ...

    # El estado del agente persistirá durante la sesión de cada modo
    agent_state = AgentState() # Estado inicial, se cambiará si el modo es orquestador

    while True:
        try:
            # ... (obtener cwd y prompt_text) ...
            user_input = session.prompt(prompt_text)

            if not user_input.strip():
                continue

            # --- Manejo de Comandos Meta ---
            # ... (salir, reset, undo, help) ...

            if user_input.lower().strip() == '%agentmode':
                if current_agent_mode == "bash":
                    current_agent_mode = "orchestrator"
                    agent_state = OrchestratorState() # Reiniciar con OrchestratorState
                else:
                    current_agent_mode = "bash"
                    agent_state = AgentState() # Reiniciar con AgentState
                print(f"Cambiado al modo '{current_agent_mode}'. Conversación reiniciada.")
                continue

            # --- Invocación del Agente ---

            # Añadir el mensaje del usuario al estado
            if current_agent_mode == "orchestrator":
                # Si es la primera interacción en modo orquestador, guardar la query
                if not agent_state.user_query:
                    agent_state.user_query = user_input
                agent_state.messages.append(HumanMessage(content=user_input))
            else:
                agent_state.messages.append(HumanMessage(content=user_input))

            active_agent_app = bash_agent_app if current_agent_mode == "bash" else orchestrator_app

            # Bucle para manejar las acciones del agente (especialmente para el orquestador)
            # Este bucle permite que el agente realice múltiples pasos internos sin requerir
            # nueva entrada del usuario, hasta que necesite una acción externa (aprobación, comando).
            while True:
                # La invocación del grafo devuelve el estado actualizado
                final_state_dict = active_agent_app.invoke(agent_state)
                agent_state = final_state_dict # El estado actual ahora es el estado final de la invocación

                # Si es el orquestador, verificar action_needed
                if current_agent_mode == "orchestrator":
                    if agent_state.action_needed == "await_user_approval":
                        # Mostrar el plan y pedir aprobación
                        if console:
                            console.print(Padding(Panel(Markdown(agent_state.plan_presentation),
                                                        border_style='yellow', title='Plan del Orquestador'), (1, 2)))
                        else:
                            print(f"\nPlan del Orquestador:\n{agent_state.plan_presentation}\n")

                        approval_input = ""
                        if auto_approve:
                            approval_input = 's'
                            if console: console.print(Padding("[yellow]Plan auto-aprobado.[/yellow]", (0, 2)))
                            else: print("Plan auto-aprobado.")
                        else:
                            while approval_input not in ['s', 'n']:
                                approval_input = input("¿Deseas aprobar este plan? (s/n): ").lower().strip()
                                if approval_input not in ['s', 'n']:
                                    print("Respuesta no válida. Por favor, responde 's' o 'n'.")

                        agent_state.user_approval = (approval_input == 's')
                        agent_state.action_needed = None # Resetear para que el agente procese la aprobación
                        # Re-invocar el grafo para que handle_approval_node procese la decisión
                        continue # Salir del bucle interno y volver a invocar el grafo

                    elif agent_state.action_needed == "execute_command":
                        command_to_execute = agent_state.command_to_execute

                        run_command = False
                        if auto_approve:
                            run_command = True
                            if console: console.print(Padding(f"[yellow]Comando auto-aprobado: `{command_to_execute}`[/yellow]", (0, 2)))
                            else: print(f"Comando auto-aprobado: `{command_to_execute}`")
                        else:
                            while True:
                                approval_input = input(f"\nEl orquestador propone ejecutar: `{command_to_execute}`\n¿Deseas ejecutarlo? (s/n): ").lower().strip()
                                if approval_input == 's':
                                    run_command = True
                                    break
                                elif approval_input == 'n':
                                    print("Comando no ejecutado.")
                                    run_command = False
                                    break
                                else:
                                    print("Respuesta no válida. Por favor, responde 's' o 'n'.")

                        full_command_output = ""
                        if run_command:
                            try:
                                if console: console.print(Padding("[yellow]Ejecutando comando...[/yellow]", (0, 2)))
                                else: print("Ejecutando comando...")

                                for output_chunk in command_executor.execute(command_to_execute, cwd=os.getcwd()):
                                    full_command_output += output_chunk
                                    print(output_chunk, end='', flush=True)
                                print()
                            except KeyboardInterrupt:
                                command_executor.terminate()
                                full_command_output = "Comando cancelado por el usuario."
                                if console: console.print(Padding("\n\n[bold red]Comando cancelado por el usuario.[/bold red]", (0, 2)))
                                else: print("\n\nComando cancelado por el usuario.")
                        else:
                            full_command_output = "Comando no ejecutado por el usuario."

                        # Alimentar la salida al agente como un ToolMessage
                        agent_state.messages.append(ToolMessage(
                            content=full_command_output,
                            tool_call_id="execute_command" # Usar un ID genérico para comandos
                        ))
                        agent_state.command_to_execute = None # Resetear el comando
                        agent_state.action_needed = None # Resetear para que el agente procese la salida
                        # Re-invocar el grafo para que handle_output_node procese la salida
                        continue # Salir del bucle interno y volver a invocar el grafo

                    elif agent_state.action_needed == "final_response" or agent_state.status in ["finished", "failed"]:
                        # Mostrar la respuesta final del orquestador
                        if console:
                            console.print(Padding(Panel(Markdown(agent_state.final_response),
                                                        border_style='green' if agent_state.status == "finished" else 'red',
                                                        title=f'KogniTerm ({current_agent_mode})'), (1, 2)))
                        else:
                            print(f"\nKogniTerm ({current_agent_mode}):\n{agent_state.final_response}\n")
                        break # Salir del bucle interno del orquestador, esperando nueva entrada del usuario

                    else:
                        # Si no hay una acción externa necesaria, el orquestador puede continuar su procesamiento interno.
                        # Por ejemplo, después de handle_output, puede pasar directamente a execute_task.
                        # Si el orquestador no ha terminado y no necesita una 'final_response' explícita,
                        # re-invocamos para que continúe su lógica interna.
                        if agent_state.status not in ["finished", "failed"]:
                            continue # Re-invocar el grafo
                        else:
                            break # El orquestador ha terminado, pero no tiene una 'final_response' explícita.
                                  # En este caso, simplemente esperamos nueva entrada del usuario.

                else: # Modo bash
                    # La lógica para el modo bash puede permanecer más simple,
                    # ya que el bash_agent.py ya maneja la confirmación y ejecución en un solo ciclo
                    # a través de command_to_confirm.
                    # El bucle while para el bash_agent ya está en terminal.py
                    # y maneja la re-invocación después de la ejecución del comando.
                    # Mostrar la respuesta final del AI para el modo bash
                    final_response_message = agent_state.messages[-1]
                    if isinstance(final_response_message, AIMessage) and final_response_message.content:
                        content = final_response_message.content
                        if not isinstance(content, str):
                            content = str(content)

                        if console:
                            console.print(Padding(Panel(Markdown(content),
                                                        border_style='blue', title=f'KogniTerm ({current_agent_mode})\''), (1, 2)))
                        else:
                            print(f"\nKogniTerm ({current_agent_mode}):\n{content}\n")
                    break # Salir del bucle interno, esperar nueva entrada del usuario

        except KeyboardInterrupt:
            print("\nSaliendo...")
            break
        except Exception as e:
            print(f"Ocurrió un error inesperado: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
```

---

### **Resumen de Beneficios de la Refactorización:**

*   **Modularidad Mejorada:** El agente orquestador es ahora una unidad más autocontenida, con su propia lógica de estado y flujo.
*   **Claridad del Flujo:** El grafo de LangGraph del orquestador define explícitamente cada fase (planificación, aprobación, ejecución, evaluación), lo que facilita la comprensión y el depurado.
*   **Flexibilidad:** Es más fácil añadir nuevos tipos de acciones o lógica de manejo de errores dentro de los nodos del orquestador sin afectar `terminal.py`.
*   **Mantenibilidad:** Los cambios en la lógica del orquestador se localizan en `orchestrator_agent.py`.
*   **Experiencia de Usuario Consistente:** La interacción de aprobación y ejecución se maneja de manera uniforme.

Esta refactorización transformará el orquestador en un componente mucho más potente y bien estructurado, capaz de manejar tareas complejas de manera más autónoma.
