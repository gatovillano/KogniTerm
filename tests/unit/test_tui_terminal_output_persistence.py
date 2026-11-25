import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget, MessageWidget
from kogniterm.terminal.tui.components.tool_output import (
    ToolOutputWidget,
    CollapsibleToolOutputWidget,
)
from kogniterm.terminal.tui.tui_app import KogniTermTUI


@pytest.mark.anyio
async def test_terminal_output_persists_after_ai_text():
    """
    Verifica que la salida de terminal (CollapsibleToolOutputWidget / ToolOutputWidget)
    no se elimine cuando el agente responde con texto/markdown posterior a la ejecución,
    y que transicione de 'Run' a 'Ran' manteniéndose colapsada por defecto.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log

        # 1. Enviar salida de terminal
        chat_log.write_stream(("__TERMINAL__", "execute_command", "salida del comando\n", "ls -la"))
        await pilot.pause()

        collapsible_widgets = [w for w in chat_log.children if isinstance(w, CollapsibleToolOutputWidget)]
        tool_widgets = list(chat_log.query(ToolOutputWidget))
        assert len(collapsible_widgets) == 1, "Debe existir un CollapsibleToolOutputWidget montado"
        assert len(tool_widgets) == 1, "Debe existir un ToolOutputWidget interno"
        assert collapsible_widgets[0].collapsed is True
        assert collapsible_widgets[0]._collapsible.title == "Run ls -la"

        # 2. Enviar respuesta de texto de la IA
        chat_log.write_stream("Aquí está el resultado del comando.")
        await pilot.pause()

        # 3. Verificar que el widget persiste y pasó a 'Ran'
        collapsible_after = [w for w in chat_log.children if isinstance(w, CollapsibleToolOutputWidget)]
        message_widgets_after = [w for w in chat_log.children if isinstance(w, MessageWidget)]

        assert len(collapsible_after) == 1, "El widget de terminal NO debe ser eliminado tras la respuesta de texto"
        assert collapsible_after[0]._collapsible.title == "Ran ls -la"
        assert collapsible_after[0].collapsed is True
        assert len(message_widgets_after) >= 1, "Debe haberse montado el MessageWidget con la respuesta"

        # 4. Expandir y comprobar que la salida interna está intacta
        collapsible_after[0].expand()
        await pilot.pause()
        assert collapsible_after[0].collapsed is False
        assert "salida del comando" in collapsible_after[0].terminal_widget.tool_content


@pytest.mark.anyio
async def test_sequential_commands_create_separate_persistent_widgets():
    """
    Verifica que la ejecución secuencial de múltiples comandos cree widgets
    separados y persistentes para cada uno, sin sobreescribir ni borrar los anteriores,
    y que el primero pase a 'Ran' cuando inicia el segundo.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log

        # Comando 1
        chat_log.write_stream(("__TERMINAL__", "execute_command", "salida 1\n", "ls"))
        await pilot.pause()

        # Comando 2 (distinto comando)
        chat_log.write_stream(("__TERMINAL__", "execute_command", "salida 2\n", "pwd"))
        await pilot.pause()

        collapsible_mid = [w for w in chat_log.children if isinstance(w, CollapsibleToolOutputWidget)]
        assert len(collapsible_mid) == 2
        assert collapsible_mid[0]._collapsible.title == "Ran ls"
        assert collapsible_mid[1]._collapsible.title == "Run pwd"

        # Respuesta IA
        chat_log.write_stream("Comandos ejecutados exitosamente.")
        await pilot.pause()

        tool_widgets = list(chat_log.query(ToolOutputWidget))
        assert len(tool_widgets) == 2, f"Deben persistir 2 ToolOutputWidget independientes, encontrados: {len(tool_widgets)}"
        assert collapsible_mid[1]._collapsible.title == "Ran pwd"


@pytest.mark.anyio
async def test_spinner_does_not_remove_tool_output():
    """
    Verifica que la activación de un spinner de carga no destruya
    los widgets de terminal existentes en el chat log.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log

        # Salida terminal
        chat_log.write_stream(("__TERMINAL__", "execute_command", "proceso terminado\n", "git status"))
        await pilot.pause()

        # Spinner
        chat_log.write_stream(("__SPINNER__", "Pensando..."))
        await pilot.pause()

        tool_widgets_during_spinner = list(chat_log.query(ToolOutputWidget))
        assert len(tool_widgets_during_spinner) == 1, "El spinner no debe eliminar el ToolOutputWidget"

        # Mensaje posterior que reemplaza el spinner
        chat_log.write_stream("Respuesta final.")
        await pilot.pause()

        tool_widgets_final = list(chat_log.query(ToolOutputWidget))
        assert len(tool_widgets_final) == 1, "El ToolOutputWidget debe persistir tras la resolución del spinner"


@pytest.mark.anyio
async def test_command_execution_does_not_create_black_rectangle_or_orphan_widget():
    """
    Verifica que al ejecutar un comando con feedback inicial (update_terminal_output con "")
    y posterior salida, no se generen widgets vacíos, rectángulos negros u orphans
    entre la notificación de herramienta y el widget de terminal.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log

        # 1. Notificación de herramienta
        chat_log.write_tool_notification("execute_command", "python3 -c 'print(1)'")
        await pilot.pause()

        # 2. Feedback inicial al comenzar la ejecución (cadena vacía)
        app.update_terminal_output("execute_command", "", command="python3 -c 'print(1)'")
        await pilot.pause()

        # 3. Flujo de salida del comando
        app.update_terminal_output("execute_command", "1\n", command="python3 -c 'print(1)'")
        await pilot.pause()

        # Comprobación de widgets montados
        collapsible_widgets = [w for w in chat_log.children if isinstance(w, CollapsibleToolOutputWidget)]
        message_widgets = [w for w in chat_log.children if isinstance(w, MessageWidget)]

        assert len(collapsible_widgets) == 1, "Debe existir un único CollapsibleToolOutputWidget"
        assert len(message_widgets) == 1, "Solo debe existir el MessageWidget de la notificación de herramienta"
        assert len(chat_log.children) == 2, f"Total de widgets debe ser 2, encontrados: {len(chat_log.children)}"
