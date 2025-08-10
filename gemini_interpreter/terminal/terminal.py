import sys
from ..core.interpreter import Interpreter # Keep import for type hinting if needed, but not for instantiation
import re

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.padding import Padding
    rich_available = True
except ImportError:
    rich_available = False

# Import the LangGraph agent and its state
from ..core.agents.bash_agent import bash_agent_app, AgentState, interpreter # Import the global interpreter instance
from ..core.agents.orchestrator_agent import orchestrator_app, OrchestratorState

def start_terminal_interface(auto_approve=False):
    
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

    while True:
        try:
            user_input = input("> ")
            if not user_input.strip():
                continue

            if user_input.lower() == 'salir':
                break

            if user_input.lower().strip() == '%reset':
                interpreter.reset()
                print("Conversación reiniciada.")
                continue

            if user_input.lower().strip() == '%help':
                print("""
Comandos disponibles:
  %help     Muestra este mensaje de ayuda.
  %reset    Reinicia la conversación.
  %undo     Deshace el último mensaje.
  salir     Sale del intérprete.
""" )
                continue

            if user_input.lower().strip() == '%undo':
                if interpreter.undo():
                    print("Último mensaje deshecho.")
                else:
                    print("No hay nada que deshacer.")
                continue

            # --- LangGraph Integration Start ---
            if user_input.lower().startswith("plan:"):
                # Invoke Orchestrator
                initial_state = OrchestratorState(user_query=user_input[len("plan:"):].strip())
                final_orchestrator_state = orchestrator_app.invoke(initial_state)
                
                plan_presentation = final_orchestrator_state.get('plan_presentation', '')
                
                if rich_available:
                    console.print(Padding(Markdown(plan_presentation), (1, 2)))
                else:
                    print(plan_presentation)

            else:
                # Invoke Bash Agent (current logic)
                initial_state = AgentState(user_message=user_input, messages=[])
                final_state = bash_agent_app.invoke(initial_state)

                gemini_response_text = final_state.get('gemini_response_text', '')
                command_to_execute = final_state.get('command_to_execute', '')

                if rich_available:
                    console.print(Padding(Markdown(gemini_response_text), (1, 2)))
                else:
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
                            for output_chunk in interpreter.executor.execute(command_to_execute):
                                full_command_output += output_chunk
                                print(output_chunk, end='', flush=True)
                            
                            interpreter.add_command_output_to_history(full_command_output)

                            if rich_available:
                                console.print(Padding("[yellow]Procesando salida del comando...[/yellow]", (1, 2)))
                            else:
                                print("\n\nProcesando salida del comando...")
                            
                            summary_prompt = f"El comando anterior produjo la siguiente salida. Por favor, resume y presenta esta salida al usuario de una manera conversacional y amigable. Usa formato Markdown si es apropiado para mejorar la legibilidad. La salida fue:\n\n```output\n{full_command_output.strip()}\n```"
                            
                            conversational_response, _ = interpreter.chat(summary_prompt, add_to_history=False)
                            
                            if rich_available:
                                console.print(Padding(Markdown(conversational_response), (1, 2)))
                            else:
                                print(conversational_response)

                        except KeyboardInterrupt:
                            interpreter.executor.terminate()
                            if rich_available:
                                console.print(Padding("\n\n[bold red]Comando cancelado por el usuario.[/bold red]", (1, 2)))
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
