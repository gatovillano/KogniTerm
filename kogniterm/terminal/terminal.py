import sys
import re
import os
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.padding import Padding
    from rich.panel import Panel
    rich_available = True
except ImportError:
    rich_available = False

# Import the LangGraph agents and their states
from ..core.agents.bash_agent import bash_agent_app, AgentState as BashAgentState, interpreter
from ..core.agents.orchestrator_agent import orchestrator_app, OrchestratorState
from langgraph.graph import StateGraph

# Initialize the current agent to bash_agent by default
current_agent_mode = "bash"

def start_terminal_interface(auto_approve=False):
    session = PromptSession(history=FileHistory('.gemini_interpreter_history'))
    
    if rich_available:
        console = Console()
        console.print(Padding("[bold green]¡Bienvenido al Intérprete de Gemini![/bold green] Escribe 'salir' para terminar.", (1, 2)))
    else:
        print("\n¡Bienvenido al Intérprete de Gemini! Escribe 'salir' para terminar.")
        print("(Para una mejor visualización, instala la librería 'rich': pip install rich)\n")

    if auto_approve:
        if rich_available:
            console.print(Padding("[bold yellow]Modo de auto-aprobación activado.[/bold yellow]", (0, 2)))
        else:
            print("Modo de auto-aprobación activado.")

    orchestrator_state = None # Initialize orchestrator state outside the loop

    while True:
        try:
            # Get the current working directory for the prompt
            cwd = interpreter.current_working_directory
            prompt_text = f"({os.path.basename(cwd)}) > "
            user_input = session.prompt(prompt_text)
            if not user_input.strip():
                continue

            if user_input.lower() == 'salir':
                break

            if user_input.lower().strip() == '%reset':
                interpreter.reset()
                orchestrator_state = None # Reset orchestrator state as well
                print("Conversación reiniciada.")
                continue

            if user_input.lower().strip() == '%help':
                print("""
Comandos disponibles:
  %help       Muestra este mensaje de ayuda.
  %reset      Reinicia la conversación.
  %undo       Deshace el último mensaje.
  %agentmode  Cambia entre el modo 'bash' y 'orchestrator'.
  salir       Sale del intérprete.
""" )
                continue

            if user_input.lower().strip() == '%undo':
                if interpreter.undo():
                    print("Último mensaje deshecho.")
                else:
                    print("No hay nada que deshacer.")
                continue
            
            global current_agent_mode
            if user_input.lower().strip() == '%agentmode':
                if current_agent_mode == "bash":
                    current_agent_mode = "orchestrator"
                    orchestrator_state = None # Reset state when switching modes
                    print("Cambiado al modo 'orchestrator'.")
                else:
                    current_agent_mode = "bash"
                    orchestrator_state = None # Reset state when switching modes
                    print("Cambiado al modo 'bash'.")
                continue

            # --- LangGraph Integration Start --- 
            
            gemini_response_text = ""
            command_to_execute = None
            
            if current_agent_mode == "bash":
                initial_state = BashAgentState(user_message=user_input, messages=[])
                final_state = bash_agent_app.invoke(initial_state)
                gemini_response_text = final_state.get('gemini_response_text', '')
                command_to_execute = final_state.get('command_to_execute', '')
            elif current_agent_mode == "orchestrator":
                # Prepare input for the orchestrator based on its current action_needed
                orchestrator_input = {"user_query": user_input}
                
                if orchestrator_state:
                    current_action_needed = orchestrator_state.get("action_needed")
                    if current_action_needed == "await_user_approval":
                        orchestrator_input["user_approval"] = user_input.lower()
                        orchestrator_input["reinvoke_for_approval"] = True
                        orchestrator_input["user_query"] = "" # Clear query for approval re-invocation
                    elif current_action_needed == "execute_command":
                        orchestrator_input["command_output"] = user_input # User input is the command output
                        orchestrator_input["user_query"] = "" # Clear query for command output re-invocation
                    elif current_action_needed == "execute_tool":
                        orchestrator_input["tool_output"] = user_input # User input is the tool output
                        orchestrator_input["user_query"] = ""

                # Prepare input for the orchestrator based on its current action_needed
                orchestrator_input = {"user_query": user_input}
                
                if orchestrator_state:
                    current_action_needed = orchestrator_state.get("action_needed")
                    if current_action_needed == "await_user_approval":
                        orchestrator_input["user_approval"] = user_input.lower()
                        orchestrator_input["reinvoke_for_approval"] = True
                        orchestrator_input["user_query"] = "" # Clear query for approval re-invocation
                    elif current_action_needed == "execute_command":
                        orchestrator_input["command_output"] = user_input # User input is the command output
                        orchestrator_input["user_query"] = "" # Clear query for command output re-invocation
                    elif current_action_needed == "execute_tool":
                        orchestrator_input["tool_output"] = user_input # User input is the tool output
                        orchestrator_input["user_query"] = ""

                # Invoke the orchestrator application with the current state
                # If orchestrator_state is None, it's the first invocation for a new query
                if orchestrator_state is None or orchestrator_state.get("status") in ["finished", "cancelled"]:
                    # Start a new orchestration if it's the first query or previous one finished/cancelled
                    final_orchestrator_state = orchestrator_app.invoke(orchestrator_input)
                else:
                    # Continue existing orchestration
                    final_orchestrator_state = orchestrator_app.invoke(orchestrator_state)

                if isinstance(final_orchestrator_state, dict):
                    orchestrator_state = final_orchestrator_state # Update the global state
                else:
                    print(f"Error: El orquestador devolvió un tipo inesperado: {type(final_orchestrator_state)}. Contenido: {final_orchestrator_state}", file=sys.stderr)
                    orchestrator_state = None
                    continue # Skip further processing for this iteration

                current_action_needed = orchestrator_state.get("action_needed")

                if current_action_needed == "present_plan":
                    if rich_available:
                        console.print(Padding(Panel(Markdown(orchestrator_state["plan_presentation"])), (1, 2)))
                    else:
                        print(orchestrator_state["plan_presentation"])
                    # The terminal will now wait for the user's next input (s/n)
                    # The orchestrator_state is preserved for the next iteration.
                    continue # Go back to the prompt to get user approval

                elif current_action_needed == "execute_command":
                    command_to_execute = orchestrator_state["command_to_execute"]
                    orchestrator_state["command_to_execute"] = "" # Clear to prevent re-execution
                    # The common command execution logic will handle this after this block.
                    
                elif current_action_needed == "execute_tool":
                    tool_calls = orchestrator_state.get("tool_calls", [])
                    if tool_calls:
                        tool_call_info = tool_calls[0]
                        tool_name = tool_call_info.get("name")
                        tool_args = tool_call_info.get("args", {})
                        
                        found_tool = next((tool for tool in interpreter.tools if tool.name == tool_name), None)
                        if found_tool:
                            try:
                                tool_output = found_tool._run(**tool_args)
                                orchestrator_state["tool_output"] = tool_output
                                orchestrator_state["tool_calls"] = [] # Clear tool calls after execution

                                tool_output_str = str(tool_output)
                                if rich_available:
                                    console.print(Padding(Panel(Markdown(f"### Salida de la Herramienta: {tool_name}\n\n```\n{tool_output_str}\n```"), border_style='green', title='Kogniterm - Herramienta', padding=1), (1, 2)))
                                else:
                                    print(f"\n--- Salida de la Herramienta: {tool_name} ---\n{tool_output_str}\n-----------------------------------\n")
                                
                                # After tool execution, re-invoke orchestrator with the output
                                # This will be handled by the next iteration of the main loop,
                                # where orchestrator_state will contain the tool_output.
                                continue # Go back to the prompt, orchestrator will process tool_output next
                            except Exception as e:
                                error_message = f"Error al ejecutar la herramienta {tool_name}: {e}"
                                orchestrator_state["tool_output"] = error_message
                                orchestrator_state["tool_calls"] = [] # Clear tool calls

                                if rich_available:
                                    console.print(Padding(Panel(f"### Error al ejecutar la Herramienta: {tool_name}\n\n```\n{error_message}\n```"), border_style='red', title='Kogniterm - Error de Herramienta', padding=1), (1, 2))
                                else:
                                    print(f"\n--- Error al ejecutar la Herramienta: {tool_name} ---\n{error_message}\n-----------------------------------\n")
                                continue # Go back to the prompt, orchestrator will process tool_output next
                        else:
                            error_message = f"Herramienta no reconocida: {tool_name}"
                            orchestrator_state["tool_output"] = error_message
                            orchestrator_state["tool_calls"] = []

                            if rich_available:
                                console.print(Padding(Panel(f"### Error: Herramienta no reconocida\n\n```\n{error_message}\n```"), border_style='red', title='Kogniterm - Error', padding=1), (1, 2))
                            else:
                                print(f"\n--- Error: Herramienta no reconocida ---\n{error_message}\n-----------------------------------\n")
                            continue # Go back to the prompt, orchestrator will process tool_output next
                    else:
                        orchestrator_state["tool_output"] = "No se encontraron llamadas a herramientas."
                        if rich_available:
                            console.print(Padding(Panel("No se encontraron llamadas a herramientas en el estado del orquestador."), border_style='yellow', title='Kogniterm - Advertencia', padding=1), (1, 2))
                        else:
                            print("No se encontraron llamadas a herramientas en el estado del orquestador.")
                        continue # Go back to the prompt, orchestrator will process tool_output next
                    
                elif current_action_needed == "respond_final":
                    gemini_response_text = orchestrator_state["final_response"]
                    orchestrator_state = None # Clear state for next new query
                    # The common response printing logic will handle this after this block.
                
                else:
                    # Fallback for unexpected action_needed or initial state
                    print(f"Advertencia: Acción inesperada del orquestador: {current_action_needed}", file=sys.stderr)
                    orchestrator_state = None # Clear state on error
                    continue # Go back to the prompt

            # Common handling for all agents after their specific logic completes
            # This part handles printing the final response and executing commands if they were set
            # by either the bash agent or the orchestrator's final step.

            if rich_available and gemini_response_text: # Only print if there's a response
                console.print(Padding(Panel(Markdown(gemini_response_text), border_style='blue', title='Kogniterm', padding=1), (1, 2)))
            elif gemini_response_text:
                print(gemini_response_text)

            if command_to_execute:
                run_command = False
                if auto_approve:
                    run_command = True
                    if rich_available:
                        console.print(Padding("[yellow]Comando auto-aprobado.[/yellow]", (0, 2)))
                    else:
                        print("Comando auto-aprobado.")
                else:
                    while True:
                        approval_input = input("¿Deseas ejecutar este comando? (s/n): ").lower().strip()
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
                    try:
                        if rich_available:
                            console.print(Padding("[yellow]Ejecutando comando... (Presiona Ctrl+C para cancelar)[/yellow]", (0, 2)))
                        else:
                            print("Ejecutando comando... (Presiona Ctrl+C para cancelar)")
                        
                        full_command_output = ""
                        for output_chunk in interpreter.executor.execute(command_to_execute, cwd=interpreter.current_working_directory):
                            full_command_output += output_chunk
                            print(output_chunk, end='', flush=True)
                        print() # Ensure a newline after command output
                        
                        if current_agent_mode == "bash": # Only add to history for bash agent
                            interpreter.add_command_output_to_history(full_command_output)

                            summary_prompt = f"El comando anterior produjo la siguiente salida. Por favor, resume y presenta esta salida al usuario de una manera conversacional y amigable, usando emojis. Usa formato Markdown si es apropiado para mejorar la legibilidad. La salida fue:\n\n```output\n{full_command_output.strip()}\n```"
                            conversational_response, _ = interpreter.chat(summary_prompt, add_to_history=False)
                            
                            if rich_available:
                                console.print(Padding(Panel(Markdown(conversational_response), border_style='blue', title='Gemini', padding=1), (1, 2)))
                            else:
                                print(conversational_response)
                            print() # Ensure a newline after Gemini's response before the next prompt
                        elif current_agent_mode == "orchestrator":
                            # If orchestrator issues a command, re-invoke it with the output
                            # This part is handled by the orchestrator invocation itself,
                            # so no action needed here.
                            pass

                    except KeyboardInterrupt:
                        interpreter.executor.terminate()
                        if rich_available:
                            console.print(Padding("\n\n[bold red]Comando cancelado por el usuario.[/bold red]", (0, 2)))
                        else:
                            print("\n\nComando cancelado por el usuario.")
                
            else:
                pass # No command to execute, no extra newline needed

            # --- LangGraph Integration End ---

        except KeyboardInterrupt:
            print("\nSaliendo del intérprete...")
            break
        except Exception as e:
            print(f"Ocurrió un error inesperado: {e}", file=sys.stderr)
