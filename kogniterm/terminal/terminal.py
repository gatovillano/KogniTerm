import asyncio
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
    from rich.spinner import Spinner
    rich_available = True
except ImportError:
    rich_available = False

# --- Importaciones de Agentes ---
from ..core.agents.bash_agent import bash_agent_app, AgentState
from ..core.agents.orchestrator_agent import orchestrator_app, OrchestratorState # <-- Importar OrchestratorState

# --- Estado Global de la Terminal ---
current_agent_mode = "bash" # Inicia en modo bash por defecto
command_executor = CommandExecutor() # Nueva instancia global

def print_welcome_banner(console):
    """Imprime el banner de bienvenida con un degradado de colores."""
    console.print() # Margen superior
    banner_text = """
██╗  ██╗ ██████╗  ██████╗ ███╗   ██╗██╗████████╗███████╗██████╗ ███╗   ███╗
██║ ██╔╝██╔═══██╗██╔════╝ ████╗  ██║██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║
█████╔╝ ██║   ██║██║  ███╗██╔██╗ ██║██║   ██║   █████╗  ██████╔╝██╔████╔██║
██╔═██╗ ██║   ██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║
██║  ██╗╚██████╔╝╚██████╔╝██║ ╚████║██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║
╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝
"""
    # Paleta de lilas y morados para un degradado más suave
    colors = [
        "#d1c4e9", # Light Lilac
        "#c5b7e0",
        "#b9aad7",
        "#ad9dce",
        "#a190c5",
        "#9583bc",
    ]
    
    lines = banner_text.strip().split('\n')
    num_lines = len(lines)
    
    for i, line in enumerate(lines):
        # Interpolar colores para un degradado más suave
        console.print(f"[{colors[i % len(colors)]}]{line}[/]", justify="center")


async def start_terminal_interface(auto_approve=False): # Re-introduciendo auto_approve
    """Inicia el bucle principal de la interfaz de la terminal."""
    global current_agent_mode
    session = PromptSession(history=FileHistory('.gemini_interpreter_history'))
    console = Console() if rich_available else None

    # Imprimir mensaje de bienvenida
    if console:
        print_welcome_banner(console) # Imprime el banner
        console.print(Padding("Escribe '%salir' para terminar o '%help' para ver los comandos.", (1, 2)), justify="center")
        console.print(f"Modo inicial: [bold cyan]{current_agent_mode}[/bold cyan]")
    else:
        # Fallback para cuando rich no está disponible
        banner_text = """
██╗  ██╗ ██████╗  ██████╗ ███╗   ██╗██╗████████╗███████╗██████╗ ███╗   ███╗
██║ ██╔╝██╔═══██╗██╔════╝ ████╗  ██║██║╚══██╔══╝██╔════╝██╔══██╗████╗ ████║
█████╔╝ ██║   ██║██║  ███╗██╔██╗ ██║██║   ██║   █████╗  ██████╔╝██╔████╔██║
██╔═██╗ ██║   ██║██║   ██║██║╚██╗██║██║   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║
██║  ██╗╚██████╔╝╚██████╔╝██║ ╚████║██║   ██║   ███████╗██║  ██║██║ ╚═╝ ██║
╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝
"""
        print(banner_text)
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
            user_input = await session.prompt_async(prompt_text)

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
                    # Iniciar con el estado correcto para el orquestador
                    agent_state = OrchestratorState()
                else:
                    current_agent_mode = "bash"
                    agent_state = AgentState() # Volver al estado simple de bash
                
                if console:
                    console.print(f"Cambiado al modo [bold cyan]{current_agent_mode}[/bold cyan]. Conversación reiniciada.")
                else:
                    print(f"Cambiado al modo '{current_agent_mode}'. Conversación reiniciada.")
                continue

            # --- Invocación del Agente ---
            
            active_agent_app = bash_agent_app if current_agent_mode == "bash" else orchestrator_app

            # Lógica para el modo ORCHESTRATOR
            if current_agent_mode == "orchestrator":
                # Si es la primera interacción, guardar la query inicial
                if not agent_state.user_query:
                    agent_state.user_query = user_input
                
                # El orquestador se maneja en un bucle hasta que termina o necesita nueva entrada
                while True:
                    with console.status("[bold green]KogniTerm está pensando...", spinner="dots"):
                        final_state_dict = await active_agent_app.ainvoke(agent_state)
                    
                    agent_state = final_state_dict

                    # 1. Esperar aprobación del plan
                    if agent_state.action_needed == "await_user_approval":
                        if console:
                            console.print(Padding(Panel(Markdown(agent_state.plan_presentation), 
                                                        border_style='yellow', title='Plan del Orquestador'), (1, 2)))
                        else:
                            print(f"\nPlan del Orquestador:\n{agent_state.plan_presentation}\n")
                        
                        approval_input = ""
                        if auto_approve:
                            approval_input = 's'
                            print("Plan auto-aprobado.")
                        else:
                            while approval_input not in ['s', 'n']:
                                approval_input = input("Respuesta (s/n): ").lower().strip()

                        agent_state.user_approval = (approval_input == 's')
                        agent_state.action_needed = None # Resetear para que el grafo continúe
                        # Re-invocar el grafo para que procese la aprobación
                        continue

                    # 2. Ejecutar un comando
                    elif agent_state.action_needed == "execute_command":
                        command_to_execute = agent_state.command_to_execute
                        run_command = False
                        if auto_approve:
                            run_command = True
                            print(f"Comando auto-aprobado: {command_to_execute}")
                        else:
                            approval_input = input(f"\nEjecutar comando: '{command_to_execute}'? (s/n): ").lower().strip()
                            if approval_input == 's':
                                run_command = True

                        full_command_output = ""
                        if run_command:
                            try:
                                for output_chunk in command_executor.execute(command_to_execute, cwd=os.getcwd()):
                                    full_command_output += output_chunk
                                    print(output_chunk, end='', flush=True)
                                print()
                            except KeyboardInterrupt:
                                command_executor.terminate()
                                full_command_output = "Comando cancelado por el usuario."
                        else:
                            full_command_output = "Comando no ejecutado por el usuario."
                        
                        agent_state.tool_output = full_command_output
                        agent_state.action_needed = None # Resetear
                        # Re-invocar para procesar la salida
                        continue

                    # 3. Mostrar respuesta final y salir del bucle del orquestador
                    elif agent_state.action_needed == "final_response":
                        if console:
                            console.print(Padding(Panel(Markdown(agent_state.final_response), 
                                                        border_style='green' if agent_state.status == "finished" else 'red', 
                                                        title=f'KogniTerm ({current_agent_mode})'), (1, 2)))
                        else:
                            print(f"\nKogniTerm ({current_agent_mode}):\n{agent_state.final_response}\n")
                        break # Salir del bucle while del orquestador
                    
                    # Si no hay acción necesaria, pero el grafo no ha terminado, algo salió mal.
                    else:
                        print("[bold red]El orquestador ha entrado en un estado inesperado. Reiniciando.[/bold red]")
                        break

            # Lógica para el modo BASH (la original)
            else:
                agent_state.messages.append(HumanMessage(content=user_input))
                with console.status("[bold green]KogniTerm está pensando...", spinner="dots"):
                    final_state_dict = await active_agent_app.ainvoke(agent_state)
                
                agent_state.messages = final_state_dict['messages']
                agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')

                if agent_state.command_to_confirm:
                    command_to_execute = agent_state.command_to_confirm
                    agent_state.command_to_confirm = None
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
                            print()
                            
                            agent_state.messages.append(ToolMessage(
                                content=full_command_output, 
                                tool_call_id="execute_command"
                            ))
                            
                            final_state_dict = await active_agent_app.ainvoke(agent_state)
                            agent_state.messages = final_state_dict['messages']
                            
                        except KeyboardInterrupt:
                            command_executor.terminate()
                            if console:
                                console.print(Padding("\n\n[bold red]Comando cancelado por el usuario.[/bold red]", (0, 2)))
                            else:
                                print("\n\nComando cancelado por el usuario.")
                            agent_state.messages.append(ToolMessage(
                                content="Comando cancelado por el usuario.", 
                                tool_call_id="execute_command"
                            ))
                            final_state_dict = await active_agent_app.ainvoke(agent_state)
                            agent_state.messages = final_state_dict['messages']
                    else:
                        agent_state.messages.append(ToolMessage(
                            content="Comando no ejecutado por el usuario.", 
                            tool_call_id="execute_command"
                        ))
                        final_state_dict = await active_agent_app.ainvoke(agent_state)
                        agent_state.messages = final_state_dict['messages']

                final_response_message = agent_state.messages[-1]
                if isinstance(final_response_message, AIMessage) and final_response_message.content:
                    content = final_response_message.content
                    if not isinstance(content, str):
                        content = str(content)

                    if console:
                        console.print(Padding(Panel(Markdown(content), 
                                                    border_style='blue', title=f'KogniTerm ({current_agent_mode})'), (1, 2)))
                    else:
                        print(f"\nKogniTerm ({current_agent_mode}):\n{content}\n")
        
        except KeyboardInterrupt:
            print("\nSaliendo...")
            break
        except Exception as e:
            print(f"Ocurrió un error inesperado: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()