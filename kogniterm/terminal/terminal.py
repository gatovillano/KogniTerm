import sys
import os
from dotenv import load_dotenv # Importar load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion

load_dotenv() # Cargar variables de entorno al inicio

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.llm_service import LLMService # Importar la CLASE LLMService
from kogniterm.core.tools.python_executor import PythonTool
from kogniterm.core.tools.file_operations_tool import FileOperationsTool # Importar FileOperationsTool para acceder a glob

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
from kogniterm.core.agents.bash_agent import create_bash_agent, AgentState, SYSTEM_MESSAGE
from kogniterm.core.agents.orchestrator_agent import create_orchestrator_agent

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
╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚╚═╝  ╚═╝╚═╝     ╚═╝
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


class FileCompleter(Completer):
    def __init__(self, file_operations_tool):
        self.file_operations_tool = file_operations_tool

    def get_completions(self, document, complete_event):
        text_before_cursor = document.text_before_cursor
        
        if '@' not in text_before_cursor:
            return # No estamos en modo de autocompletado de archivos

        # Extraer la parte relevante para el autocompletado después del último '@'
        current_input_part = text_before_cursor.split('@')[-1]
        
        base_path = os.getcwd()

        # Determinar si se deben incluir archivos y directorios ocultos
        include_hidden = current_input_part.startswith('.')

        try:
            # Usar _list_directory con recursive=True para obtener todos los archivos y directorios
            # Esto devuelve rutas relativas al base_path
            all_relative_items = self.file_operations_tool._list_directory(path=base_path, recursive=True, include_hidden=include_hidden)
            
            suggestions = []
            for relative_item_path in all_relative_items:
                # Construir la ruta absoluta para verificar si es un directorio
                absolute_item_path = os.path.join(base_path, relative_item_path)
                
                display_item = relative_item_path
                if os.path.isdir(absolute_item_path):
                    display_item += '/'

                # Filtrar por el input actual del usuario
                if current_input_part.lower() in display_item.lower():
                    suggestions.append(display_item)
            
            # Ordenar las sugerencias para una mejor experiencia de usuario
            suggestions.sort()

            for suggestion in suggestions:
                # Calcular la posición de inicio para el reemplazo
                # Queremos reemplazar solo la parte que el usuario está escribiendo después del '@'
                start_position = -len(current_input_part)
                yield Completion(suggestion, start_position=start_position)

        except Exception as e:
            # Loggear el error para depuración, pero no romper la interfaz
            print(f"Error en FileCompleter: {e}", file=sys.stderr)


def start_terminal_interface(llm_service: LLMService, auto_approve=False): # Re-introduciendo auto_approve
    """Inicia el bucle principal de la interfaz de la terminal."""
    global current_agent_mode
    
    # Obtener la instancia de FileOperationsTool
    file_operations_tool = llm_service.get_tool("file_operations")
    if not file_operations_tool:
        print("Advertencia: La herramienta 'file_operations' no se encontró. El autocompletado de archivos no estará disponible.", file=sys.stderr)
        completer = None
    else:
        completer = FileCompleter(file_operations_tool)

    session = PromptSession(history=FileHistory('.gemini_interpreter_history'), completer=completer) # Pasar el completer
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
╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═╝   ╚═╝   ╚══════╝╚╚═╝  ╚═╝╚═╝     ╚═╝
"""
        print(banner_text)
        print("\n¡Bienvenido a KogniTerm! Escribe '%salir' para terminar.")
        print(f"Modo inicial: {current_agent_mode}")

    if console and auto_approve: # Nuevo mensaje de auto_approve
        console.print(Padding("[bold yellow]Modo de auto-aprobación activado.[/bold yellow]", (0, 2)))
    elif auto_approve:
        print("Modo de auto-aprobación activado.")

    # Crear las instancias de los agentes con la instancia de llm_service de la terminal
    bash_agent_app = create_bash_agent(llm_service)
    orchestrator_app = create_orchestrator_agent(llm_service)

    # El estado del agente persistirá durante la sesión de cada modo
    agent_state = AgentState()
    # Usar el historial de llm_service directamente como el estado del agente
    agent_state.messages = llm_service.conversation_history
    
    # Asegurarse de que el SYSTEM_MESSAGE esté siempre al principio del historial.
    # Si el historial cargado ya contiene el SYSTEM_MESSAGE, no lo añadimos de nuevo.
    if not agent_state.messages or not (isinstance(agent_state.messages[0], SystemMessage) and agent_state.messages[0].content == SYSTEM_MESSAGE.content):
        # Si el historial no está vacío y el primer mensaje no es el SYSTEM_MESSAGE,
        # o si el historial está vacío, añadir el SYSTEM_MESSAGE al principio.
        if agent_state.messages and not (isinstance(agent_state.messages[0], SystemMessage) and agent_state.messages[0].content == SYSTEM_MESSAGE.content):
            agent_state.messages.insert(0, SYSTEM_MESSAGE)
        elif not agent_state.messages:
            agent_state.messages.append(SYSTEM_MESSAGE)
    
    # Filtrar cualquier SYSTEM_MESSAGE duplicado del historial si ya lo hemos añadido
    # Esto es importante si el historial cargado ya tenía SYSTEM_MESSAGE y lo insertamos de nuevo.
    # Solo mantenemos la primera instancia del SYSTEM_MESSAGE.
    system_message_count = sum(1 for msg in agent_state.messages if isinstance(msg, SystemMessage) and msg.content == SYSTEM_MESSAGE.content)
    if system_message_count > 1:
        first_system_message_index = -1
        for i, msg in enumerate(agent_state.messages):
            if isinstance(msg, SystemMessage) and msg.content == SYSTEM_MESSAGE.content:
                if first_system_message_index == -1:
                    first_system_message_index = i
                else:
                    agent_state.messages.pop(i)
                    break # Asumimos que solo hay un duplicado a eliminar

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
                # También reiniciamos el historial de llm_service al resetear la conversación
                llm_service.conversation_history = []
                # ¡IMPORTANTE! Re-añadir el SYSTEM_MESSAGE después de resetear
                llm_service.conversation_history.append(SYSTEM_MESSAGE)
                print(f"Conversación reiniciada para el modo '{current_agent_mode}'.")
                continue

            if user_input.lower().strip() == '%agentmode':
                if current_agent_mode == "bash":
                    current_agent_mode = "orchestrator"
                else:
                    current_agent_mode = "bash"
                agent_state = AgentState() # Reiniciar estado al cambiar de modo
                # También reiniciamos el historial de llm_service al cambiar de modo
                llm_service.conversation_history = []
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
  %compress   Resume el historial de conversación actual.
  %salir      Sale del intérprete.
""")
                continue

            if user_input.lower().strip() == '%compress':
                if console:
                    console.print(Padding("[yellow]Resumiendo historial de conversación...[/yellow]", (0, 2)))
                else:
                    print("Resumiendo historial de conversación...")
                
                summary = llm_service.summarize_conversation_history()
                
                if summary.startswith("Error") or summary.startswith("No se pudo"):
                    if console:
                        console.print(Padding(f"[red]{summary}[/red]", (0, 2)))
                    else:
                        print(summary)
                else:
                    # Reemplazar el historial con el SYSTEM_MESSAGE y el resumen
                    llm_service.conversation_history = [SYSTEM_MESSAGE, AIMessage(content=summary)]
                    agent_state.messages = llm_service.conversation_history
                    if console:
                        console.print(Padding(Panel(Markdown(summary), 
                                                    border_style='green', title='Historial Comprimido'), (1, 2)))
                    else:
                        print(f"""Historial comprimido:
{summary}""")
                continue

            # --- Invocación del Agente ---
            
            # Eliminar el '@' del inicio si existe, ya que es solo para el autocompletado de la terminal
            processed_input = user_input.strip()
            if processed_input.startswith('@'):
                processed_input = processed_input[1:] # Eliminar el primer '@'

            # Añadir el mensaje del usuario al estado
            agent_state.messages.append(HumanMessage(content=processed_input))

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

            # --- Manejo de la salida de PythonTool ---
            if isinstance(final_response_message, ToolMessage) and final_response_message.tool_call_id == "python_executor":
                # Asumiendo que la instancia de PythonTool está disponible a través de llm_service
                python_tool_instance = llm_service.get_tool("python_executor")
                if python_tool_instance and hasattr(python_tool_instance, 'get_last_structured_output'):
                    structured_output = python_tool_instance.get_last_structured_output()
                    if structured_output and "result" in structured_output:
                        if console:
                            console.print(Padding(Panel("[bold green]Salida del Código Python:[/bold green]", border_style='green'), (1, 2)))
                        else:
                            print("\n--- Salida del Código Python ---\n")

                        for item in structured_output["result"]:
                            if item['type'] == 'stream':
                                if console:
                                    console.print(f"[cyan]STDOUT:[/cyan] {item['text']}")
                                else:
                                    print(f"STDOUT: {item['text']}")
                            elif item['type'] == 'error':
                                if console:
                                    console.print(f"[red]ERROR ({item['ename']}):[/red] {item['evalue']}")
                                    console.print(f"[red]TRACEBACK:[/red]\n{'' .join(item['traceback'])}")
                                else:
                                    print(f"ERROR ({item['ename']}): {item['evalue']}")
                                    print(f"TRACEBACK:\n{'' .join(item['traceback'])}")
                            elif item['type'] == 'execute_result':
                                data_str = item['data'].get('text/plain', str(item['data']))
                                if console:
                                    console.print(f"[green]RESULTADO:[/green] {data_str}")
                                else:
                                    print(f"RESULTADO: {data_str}")
                            elif item['type'] == 'display_data':
                                if 'image/png' in item['data']:
                                    if console:
                                        console.print("[magenta]IMAGEN PNG GENERADA[/magenta]")
                                    else:
                                        print("IMAGEN PNG GENERADA")
                                elif 'text/html' in item['data']:
                                    if console:
                                        console.print(f"[magenta]HTML GENERADO:[/magenta] {item['data']['text/html'][:100]}...")
                                    else:
                                        print(f"HTML GENERADO: {item['data']['text/html'][:100]}...")
                                else:
                                    if console:
                                        console.print(f"[magenta]DATOS DE VISUALIZACIÓN:[/magenta] {str(item['data'])}")
                                    else:
                                        print(f"DATOS DE VISUALIZACIÓN: {str(item['data'])}")
                        if console:
                            console.print(Padding(Panel("[bold green]Fin de la Salida Python[/bold green]", border_style='green'), (1, 2)))
                        else:
                            print("\n--- Fin de la Salida Python ---\n")
                    elif "error" in structured_output:
                        if console:
                            console.print(f"[red]Error en la ejecución de Python:[/red] {structured_output['error']}")
                        else:
                            print(f"Error en la ejecución de Python: {structured_output['error']}")
                # No imprimir el ToolMessage crudo si ya lo hemos manejado
                continue # Salir del if para no procesar como AIMessage
            # --- Manejo de la salida de FileOperationsTool ---
            elif isinstance(final_response_message, ToolMessage) and final_response_message.tool_call_id == "file_operations":
                import re
                # Convertir content a str para evitar errores de tipado
                content_str = str(final_response_message.content)
                file_content_match = re.match(r"FILE_CONTENT_START: (.*?)\n(.*)\n:FILE_CONTENT_END", content_str, re.DOTALL)
                if file_content_match:
                    file_path_read = file_content_match.group(1)
                    if console:
                        console.print(Padding(Panel(f"[bold green]Contenido del archivo '{file_path_read}' cargado para el LLM.[/bold green]", border_style='green'), (1, 2)))
                    else:
                        print(f"\n--- Contenido del archivo '{file_path_read}' cargado para el LLM. ---\n")
                    # No es necesario modificar final_response_message.content aquí, ya que el LLM ya lo tiene completo.
                    continue # Salir del if para no procesar como AIMessage
                else:
                    # Para otras operaciones de file_operations (write, delete, list, create)
                    if console:
                        console.print(Padding(Panel(f"[bold green]Operación de archivo:[/bold green]\n{final_response_message.content}", border_style='green'), (1, 2)))
                    else:
                        print(f"\n--- Operación de archivo ---\n{final_response_message.content}\n")
                    continue # Salir del if para no procesar como AIMessage

            if isinstance(final_response_message, AIMessage) and final_response_message.content:
                content = final_response_message.content
                if not isinstance(content, str):
                    content = str(content)

                if console:
                    console.print(Padding(Panel(Markdown(content), 
                                                border_style='blue', title=f'KogniTerm ({current_agent_mode})'), (1, 2)))
                else:
                    print(f"\nKogniTerm ({current_agent_mode}):\n{content}\n")
            
            # No es necesario actualizar agent_state.messages aquí de nuevo, ya está actualizado

            # --- MODIFICACIÓN 2: Guardar el historial después de cada interacción ---
            llm_service._save_history(agent_state.messages)
            # ----------------------------------------------------------------------

        except KeyboardInterrupt:
            print("\nSaliendo...")
            break
        except Exception as e:
            print(f"Ocurrió un error inesperado: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

def main():
    """Función principal para iniciar la terminal de KogniTerm."""
    # Inicializar LLMService aquí, ya que es necesario para start_terminal_interface
    llm_service = LLMService()
    start_terminal_interface(llm_service)

if __name__ == "__main__":
    main()
