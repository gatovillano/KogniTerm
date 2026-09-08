import pytest
from unittest.mock import MagicMock
from kogniterm.terminal.tui.components.chat_log import ChatLogWidget, MessageWidget
from kogniterm.terminal.tui.components.tool_output import ToolOutputWidget
from kogniterm.terminal.tui.tui_app import KogniTermTUI


@pytest.mark.anyio
async def test_terminal_output_persists_after_ai_text():
    """
    Verifica que la salida de terminal (ToolOutputWidget) no se elimine
    cuando el agente responde con texto/markdown posterior a la ejecución.
    """
    llm_service = MagicMock()
    llm_service.model_name = "test-model"
    app = KogniTermTUI(llm_service=llm_service)

    async with app.run_test() as pilot:
        chat_log = app.chat_log

        # 1. Enviar salida de terminal
        chat_log.write_stream(("__TERMINAL__", "execute_command", "salida del comando\n", "ls -la"))
        await pilot.pause()

        tool_widgets = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        assert len(tool_widgets) == 1, "Debe existir un ToolOutputWidget montado"

        # 2. Enviar respuesta de texto de la IA
        chat_log.write_stream("Aquí está el resultado del comando.")
        await pilot.pause()

        # 3. Verificar que ToolOutputWidget sigue existiendo junto con MessageWidget
        tool_widgets_after = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        message_widgets_after = [w for w in chat_log.children if isinstance(w, MessageWidget)]

        assert len(tool_widgets_after) == 1, "El ToolOutputWidget NO debe ser eliminado tras la respuesta de texto"
        assert len(message_widgets_after) >= 1, "Debe haberse montado el MessageWidget con la respuesta"


@pytest.mark.anyio
async def test_sequential_commands_create_separate_persistent_widgets():
    """
    Verifica que la ejecución secuencial de múltiples comandos cree widgets
    separados y persistentes para cada uno, sin sobreescribir ni borrar los anteriores.
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

        # Respuesta IA
        chat_log.write_stream("Comandos ejecutados exitosamente.")
        await pilot.pause()

        tool_widgets = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        assert len(tool_widgets) == 2, f"Deben persistir 2 ToolOutputWidget independientes, encontrados: {len(tool_widgets)}"


@pytest.mark.anyio
async def test_spinner_does_not_remove_tool_output():
    """
    Verifica que la activación de un spinner de carga no destruya
    los ToolOutputWidget existentes en el chat log.
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

        tool_widgets_during_spinner = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        assert len(tool_widgets_during_spinner) == 1, "El spinner no debe eliminar el ToolOutputWidget"

        # Mensaje posterior que reemplaza el spinner
        chat_log.write_stream("Respuesta final.")
        await pilot.pause()

        tool_widgets_final = [w for w in chat_log.children if isinstance(w, ToolOutputWidget)]
        assert len(tool_widgets_final) == 1, "El ToolOutputWidget debe persistir tras la resolución del spinner"
