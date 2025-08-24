import sys
import os
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from ..core.command_executor import CommandExecutor # Nueva importación

# --- Estilo de la Interfaz (Rich) ---
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.padding import Padding
    from rich.panel import Panel
    rich_available = True
except ImportError:
    rich_available = False

# --- Importaciones de Agentes ---
from ..core.agents.bash_agent import bash_agent_app, AgentState
from ..core.agents.orchestrator_agent import orchestrator_app

# --- Estado Global de la Terminal ---
current_agent_mode = "bash" # Inicia en modo bash por defecto
command_executor = CommandExecutor() # Nueva instancia global

def start_terminal_interface(auto_approve=False): # Re-introduciendo auto_approve
    """Inicia el bucle principal de la interfaz de la terminal."""
    global current_agent_mode
    session = PromptSession(history=FileHistory('.gemini_interpreter_history'))
    console = Console() if rich_available else None

    # Imprimir mensaje de bienvenida
    if console:
        console.print(Padding("[bold green]¡Bienvenido a KogniTerm![/bold green] Escribe '%salir' para terminar.", (1, 2)))
        console.print(f"Modo inicial: [bold cyan]{current_agent_mode}[/bold cyan]")
    else:
        print("\n¡Bienvenido a KogniTerm! Escribe '%salir' para terminar.")
        print(f"Modo inicial: {current_agent_mode}")

    if console and auto_approve: # Nuevo mensaje de auto_approve
        console.print(Padding("[bold yellow]Modo de auto-aprobación activado.[/bold yellow]", (0, 2)))
    elif auto_approve:
        print("Modo de auto-aprobación activado.")

    # El estado del agente persistirá durante la sesión de cada modo
    agent_state = AgentState()

    while True:
        try:
            # Obtener el directorio de trabajo actual para el prompt
            cwd = os.getcwd()
            prompt_text = f"({current_agent_mode}) ({os.path.basename(cwd)}) > "
            user_input = session.prompt(prompt_text)

            if not user_input.strip():
                continue

            # --- Manejo de Comandos Meta ---
            if user_input.lower().strip() in ['%salir', 'salir', 'exit']:
                break

            if user_input.lower().strip() == '%reset':
                agent_state = AgentState() # Reiniciar el estado
                print(f"Conversación reiniciada para el modo '{current_agent_mode}'.")
                continue

            if user_input.lower().strip() == '%agentmode':
                if current_agent_mode == "bash":
                    current_agent_mode = "orchestrator"
                else:
                    current_agent_mode = "bash"
                agent_state = AgentState() # Reiniciar estado al cambiar de modo
                print(f"Cambiado al modo '{current_agent_mode}'. Conversación reiniciada.")
                continue

            if user_input.lower().strip() == '%undo':
                # El undo ahora debe considerar el mensaje de sistema inicial
                if len(agent_state.messages) >= 3:
                    agent_state.messages.pop() # Eliminar respuesta del AI
                    agent_state.messages.pop() # Eliminar input del usuario
                    print("Última interacción deshecha.")
                else:
                    print("No hay nada que deshacer.")
                continue
            
            if user_input.lower().strip() == '%help':
                print("""
Comandos disponibles:
  %help       Muestra este mensaje de ayuda.
  %reset      Reinicia la conversación del modo actual.
  %agentmode  Cambia entre el modo 'bash' y 'orchestrator'.
  %undo       Deshace la última interacción.
  %salir      Sale del intérprete.
""" )
                continue

            # --- Invocación del Agente ---
            
            # Añadir el mensaje del usuario al estado
            agent_state.messages.append(HumanMessage(content=user_input))

            # Seleccionar el agente activo e invocarlo
            active_agent_app = bash_agent_app if current_agent_mode == "bash" else orchestrator_app
            final_state_dict = active_agent_app.invoke(agent_state)

            # Actualizar el estado para la siguiente iteración
            agent_state.messages = final_state_dict['messages']
            agent_state.command_to_confirm = final_state_dict.get('command_to_confirm') # Obtener comando a confirmar

            # --- Manejo de Confirmación de Comandos ---
            if agent_state.command_to_confirm:
                command_to_execute = agent_state.command_to_confirm
                agent_state.command_to_confirm = None # Limpiar el comando después de obtenerlo

                run_command = False
                if auto_approve:
                    run_command = True
                    if console:
                        console.print(Padding("[yellow]Comando auto-aprobado.[/yellow]", (0, 2)))
                    else:
                        print("Comando auto-aprobado.")
                else:
                    while True:
                        approval_input = input(f"\n¿Deseas ejecutar este comando? (s/n): {command_to_execute}\n").lower().strip()
                        if approval_input == 's':
                            run_command = True
                            break
                        elif approval_input == 'n':
                            print("Comando no ejecutado.")
                            run_command = False
                            break
                        else:
                            print("Respuesta no válida. Por favor, responde 's' o 'n'.")

                if run_command:
                    full_command_output = ""
                    try:
                        if console:
                            console.print(Padding("[yellow]Ejecutando comando... (Presiona Ctrl+C para cancelar)[/yellow]", (0, 2)))
                        else:
                            print("Ejecutando comando... (Presiona Ctrl+C para cancelar)")
                        
                        for output_chunk in command_executor.execute(command_to_execute, cwd=os.getcwd()):
                            full_command_output += output_chunk
                            print(output_chunk, end='', flush=True)
                        print() # Asegurar un salto de línea después de la salida del comando
                        
                        # Alimentar la salida al agente como un ToolMessage
                        agent_state.messages.append(ToolMessage(
                            content=full_command_output, 
                            tool_call_id="execute_command" # Usar el nombre de la herramienta como ID por simplicidad
                        ))
                        
                        # Re-invocar al agente para procesar la salida del comando
                        final_state_dict = active_agent_app.invoke(agent_state)
                        agent_state.messages = final_state_dict['messages'] # Actualizar estado de nuevo
                        
                    except KeyboardInterrupt:
                        command_executor.terminate()
                        if console:
                            console.print(Padding("\n\n[bold red]Comando cancelado por el usuario.[/bold red]", (0, 2)))
                        else:
                            print("\n\nComando cancelado por el usuario.")
                        # Señalizar al agente que el comando fue cancelado
                        agent_state.messages.append(ToolMessage(
                            content="Comando cancelado por el usuario.", 
                            tool_call_id="execute_command"
                        ))
                        final_state_dict = active_agent_app.invoke(agent_state)
                        agent_state.messages = final_state_dict['messages']
                else:
                    # Si el comando no se ejecutó, señalizar al agente
                    agent_state.messages.append(ToolMessage(
                        content="Comando no ejecutado por el usuario.", 
                        tool_call_id="execute_command"
                    ))
                    final_state_dict = active_agent_app.invoke(agent_state)
                    agent_state.messages = final_state_dict['messages']

            # La respuesta final del AI es el último mensaje en el estado
            final_response_message = agent_state.messages[-1] # Usar agent_state.messages directamente

            if isinstance(final_response_message, AIMessage) and final_response_message.content:
                if console:
                    console.print(Padding(Panel(Markdown(final_response_message.content), 
                                                border_style='blue', title=f'KogniTerm ({current_agent_mode})'), (1, 2)))
                else:
                    print(f"\nKogniTerm ({current_agent_mode}):\n{final_response_message.content}\n")
            
            # No es necesario actualizar agent_state.messages aquí de nuevo, ya está actualizado

        except KeyboardInterrupt:
            print("\nSaliendo...")
            break
        except Exception as e:
            print(f"Ocurrió un error inesperado: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
