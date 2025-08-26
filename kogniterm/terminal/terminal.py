import asyncio
import sys
import os
import json # Nueva importación para manejar JSON
from typing import List # Importar List

os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = ''
import argparse # Added for argument parsing
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage, SystemMessage # Añadir BaseMessage y SystemMessage
from ..core.command_executor import CommandExecutor

# Cargar variables de entorno desde .env
load_dotenv()

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

# --- Constantes ---
CONVERSATION_HISTORY_FILE = ".kogniterm_conversation_history.json"

# --- Estado Global de la Terminal ---
current_agent_mode = "bash" # Inicia en modo bash por defecto
command_executor = CommandExecutor() # Nueva instancia global

# --- Funciones de Persistencia del Historial ---
def _load_conversation_history() -> List[BaseMessage]:
    """Carga el historial de conversación desde un archivo JSON."""
    if os.path.exists(CONVERSATION_HISTORY_FILE):
        with open(CONVERSATION_HISTORY_FILE, 'r', encoding='utf-8') as f:
            try:
                raw_messages = json.load(f)
                messages = []
                for msg_data in raw_messages:
                    if msg_data['type'] == 'human':
                        messages.append(HumanMessage(content=msg_data['content']))
                    elif msg_data['type'] == 'ai':
                        messages.append(AIMessage(content=msg_data['content'], tool_calls=msg_data.get('tool_calls')))
                    elif msg_data['type'] == 'tool':
                        messages.append(ToolMessage(content=msg_data['content'], tool_call_id=msg_data['tool_call_id']))
                    elif msg_data['type'] == 'system':
                        messages.append(SystemMessage(content=msg_data['content']))
                return messages
            except json.JSONDecodeError:
                print(f"Advertencia: El archivo de historial '{CONVERSATION_HISTORY_FILE}' está corrupto. Se iniciará un nuevo historial.", file=sys.stderr)
                return []
    return []

def _save_conversation_history(messages: List[BaseMessage]):
    """Guarda el historial de conversación en un archivo JSON."""
    serializable_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            serializable_messages.append({'type': 'human', 'content': msg.content})
        elif isinstance(msg, AIMessage):
            serializable_messages.append({'type': 'ai', 'content': msg.content, 'tool_calls': msg.tool_calls})
        elif isinstance(msg, ToolMessage):
            serializable_messages.append({'type': 'tool', 'content': msg.content, 'tool_call_id': msg.tool_call_id})
        elif isinstance(msg, SystemMessage):
            serializable_messages.append({'type': 'system', 'content': msg.content})
    
    with open(CONVERSATION_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(serializable_messages, f, ensure_ascii=False, indent=2)


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
    # Cargar el historial de conversación existente
    initial_messages = _load_conversation_history()
    # El estado del agente persistirá durante la sesión de cada modo
    if current_agent_mode == "orchestrator":
        agent_state = OrchestratorState(messages=initial_messages)
    else:
        agent_state = AgentState(messages=initial_messages)

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
                if console:
                    console.print(f"Conversación reiniciada para el modo '[bold cyan]{current_agent_mode}[/bold cyan]'.")
                else:
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
                # El orquestador se maneja en un bucle hasta que termina o necesita nueva entrada
                while True:
                    # Si es la primera interacción, guardar la query inicial
                    # Si es la primera interacción, guardar la query inicial
                    # Solo aplica si agent_state es OrchestratorState
                    if isinstance(agent_state, OrchestratorState) and not agent_state.user_query:
                        agent_state.user_query = user_input
                    
                    if console: # Añadir comprobación para console
                        with console.status("[bold green]KogniTerm está pensando...", spinner="dots"):
                            # Asegurarse de que el tipo de agent_state sea correcto para la invocación
                            if isinstance(agent_state, OrchestratorState):
                                final_state_dict = await active_agent_app.ainvoke(agent_state)
                            else: # Esto no debería ocurrir si el modo es "orchestrator"
                                raise TypeError("El estado del agente no es OrchestratorState en modo orchestrator.")
                    else:
                        if isinstance(agent_state, OrchestratorState):
                            final_state_dict = await active_agent_app.ainvoke(agent_state)
                        else:
                            raise TypeError("El estado del agente no es OrchestratorState en modo orchestrator.")
                    
                    # Convertir el diccionario de estado de LangGraph de nuevo a OrchestratorState
                    agent_state = OrchestratorState(**final_state_dict)

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
                            if console:
                                console.print("[yellow]Plan auto-aprobado.[/yellow]")
                            else:
                                print("Plan auto-aprobado.")
                        else:
                            while approval_input not in ['s', 'n']:
                                approval_input = (await session.prompt_async("Respuesta (s/n): ")).lower().strip()

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
                            if console:
                                console.print(f"[yellow]Comando auto-aprobado: {command_to_execute}[/yellow]")
                            else:
                                print(f"Comando auto-aprobado: {command_to_execute}")
                        else:
                            approval_input = (await session.prompt_async(f"\nEjecutar comando: '{command_to_execute}'? (s/n): ")).lower().strip()
                            if approval_input == 's':
                                run_command = True

                        full_command_output = ""
                        if run_command:
                            try:
                                if console:
                                    with console.status("[bold green]Ejecutando comando...", spinner="dots"):
                                        for output_chunk in command_executor.execute(command_to_execute, cwd=os.getcwd()):
                                            full_command_output += output_chunk
                                            console.print(output_chunk, end='', highlight=False)
                                            console.file.flush() # Forzar el flush de la consola de rich
                                else:
                                    for output_chunk in command_executor.execute(command_to_execute, cwd=os.getcwd()):
                                        full_command_output += output_chunk
                                        print(output_chunk, end='', flush=True)
                                if console:
                                    console.print()
                                else:
                                    print()
                            except KeyboardInterrupt:
                                command_executor.terminate()
                                full_command_output = "Comando cancelado por el usuario."
                                if console:
                                    console.print(Padding("\n\n[bold red]Comando cancelado por el usuario.[/bold red]", (0, 2)))
                                else:
                                    print("\n\nComando cancelado por el usuario.")
                        else:
                            full_command_output = "Comando no ejecutado por el usuario."
                            if console:
                                console.print("[yellow]Comando no ejecutado por el usuario.[/yellow]")
                            else:
                                print("Comando no ejecutado por el usuario.")
                        
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
                        if console:
                            console.print(Padding(Panel("[bold red]El orquestador ha entrado en un estado inesperado. Reiniciando.[/bold red]", border_style='red'), (1,2)))
                        else:
                            print("[bold red]El orquestador ha entrado en un estado inesperado. Reiniciando.[/bold red]")
                        break

            # Lógica para el modo BASH
            else:
                agent_state.messages.append(HumanMessage(content=user_input))
                
                # Bucle para manejar la ejecución secuencial o confirmación de comandos
                while True:
                    if console:
                        with console.status("[bold green]KogniTerm está pensando...", spinner="dots"):
                            final_state_dict = await active_agent_app.ainvoke(agent_state) # type: ignore
                    else:
                        final_state_dict = await active_agent_app.ainvoke(agent_state) # type: ignore
                    
                    agent_state.messages = final_state_dict['messages']
                    agent_state.internal_continue = final_state_dict.get('internal_continue', False)
                    agent_state.command_to_confirm = final_state_dict.get('command_to_confirm')
                    
                    # Guardar el historial de conversación después de cada interacción del agente
                    _save_conversation_history(agent_state.messages)

                    # Si el LLM necesita continuar internamente, el bucle se repite sin pedir input al usuario
                    if agent_state.internal_continue:
                        continue
                    
                    # Si hay un comando para confirmar
                    if agent_state.command_to_confirm:
                        command_to_execute = agent_state.command_to_confirm
                        agent_state.command_to_confirm = None # Resetear para que no se pida de nuevo
                        run_command = False
                        if auto_approve:
                            run_command = True
                            if console:
                                console.print(Padding(f"[yellow]Comando auto-aprobado: {command_to_execute}[/yellow]", (0, 2)))
                            else:
                                print(f"Comando auto-aprobado: {command_to_execute}")
                        else:
                            while True:
                                approval_input = (await session.prompt_async(f"\n¿Deseas ejecutar este comando? (s/n): {command_to_execute}\n")).lower().strip()
                                if approval_input == 's':
                                    run_command = True
                                    break
                                elif approval_input == 'n':
                                    if console:
                                        console.print("[yellow]Comando no ejecutado.[/yellow]")
                                    else:
                                        print("Comando no ejecutado.")
                                    run_command = False
                                    break
                                else:
                                    if console:
                                        console.print("[red]Respuesta no válida. Por favor, responde 's' o 'n'.[/red]")
                                    else:
                                        print("Respuesta no válida. Por favor, responde 's' o 'n'.")

                        full_command_output = ""
                        if run_command:
                            try:
                                if console:
                                    console.print(Padding("[yellow]Ejecutando comando... (Presiona Ctrl+C para cancelar)[/yellow]", (0, 2)))
                                else:
                                    print("Ejecutando comando... (Presiona Ctrl+C para cancelar)")
                                
                                if console:
                                    with console.status("[bold green]Ejecutando comando...", spinner="dots"):
                                        for output_chunk in command_executor.execute(command_to_execute, cwd=os.getcwd()):
                                            full_command_output += output_chunk
                                            console.print(output_chunk, end='', highlight=False)
                                            console.file.flush() # Forzar el flush de la consola de rich
                                else:
                                    for output_chunk in command_executor.execute(command_to_execute, cwd=os.getcwd()):
                                        full_command_output += output_chunk
                                        print(output_chunk, end='', flush=True)
                                if console:
                                    console.print()
                                else:
                                    print()
                                
                                # Añadir la salida del comando al historial como ToolMessage
                                agent_state.messages.append(ToolMessage(
                                    content=full_command_output,
                                    tool_call_id="execute_command" # Usar el nombre de la herramienta
                                ))
                                
                                # Re-invocar el agente para que procese la salida del comando
                                continue # Continúa el bucle while True para que el agente procese la salida
                                
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
                                # Re-invocar para que el agente sepa que el comando fue cancelado
                                continue # Continúa el bucle while True

                        else: # Comando no ejecutado
                            agent_state.messages.append(ToolMessage(
                                content="Comando no ejecutado por el usuario.",
                                tool_call_id="execute_command"
                            ))
                            # Re-invocar para que el agente sepa que el comando no fue ejecutado
                            continue # Continúa el bucle while True
                    
                    # Si no hay comando para confirmar y no hay continuación interna,
                    # significa que el agente ha terminado su ciclo y tiene una respuesta final para el usuario.
                    final_response_message = agent_state.messages[-1]
                    if isinstance(final_response_message, AIMessage) and final_response_message.content:
                        content = final_response_message.content
                        if not isinstance(content, str):
                            content = str(content) # Asegurarse de que el contenido sea string
    
                        if console:
                            console.print(Padding(Panel(Markdown(content),
                                                        border_style='blue', title=f'KogniTerm ({current_agent_mode})'), (1, 2)))
                        else:
                            print(f"\nKogniTerm ({current_agent_mode}):\n{content}\n")
                    break # Salir del bucle while True del modo bash
          
        except KeyboardInterrupt:
            if console:
                console.print("\nSaliendo...")
            else:
                print("\nSaliendo...")
            break
        except Exception as e:
            if console:
                console.print(f"[bold red]Ocurrió un error inesperado: {e}[/bold red]")
            else:
                print(f"Ocurrió un error inesperado: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="KogniTerm: Un asistente de IA experto en terminal.")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-aprobar todas las acciones.")
    args = parser.parse_args()
    
    asyncio.run(start_terminal_interface(auto_approve=args.yes))

if __name__ == "__main__":
    main()