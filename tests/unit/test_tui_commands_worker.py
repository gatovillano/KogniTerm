from unittest.mock import MagicMock, AsyncMock
import pytest
from kogniterm.terminal.tui.tui_app import KogniTermTUI

class DummyChatInput:
    def __init__(self, value):
        self.value = value
        self.id = "chat_input"

class DummyEvent:
    def __init__(self, value):
        self.value = value
        self.input = DummyChatInput(value)

@pytest.mark.anyio
async def test_on_chat_input_submitted_intercepts_models_as_worker():
    # Instanciamos la TUI sin llamar a __init__ para evitar efectos secundarios
    app = KogniTermTUI.__new__(KogniTermTUI)
    
    # Mock del command_processor y del método run_worker
    app.command_processor = MagicMock()
    app.command_processor.process_command = AsyncMock(return_value=True)
    app.run_worker = MagicMock()
    app.on_input_submitted = AsyncMock()
    
    # Crear un evento para el comando /models
    event = DummyEvent("/models")
    
    # Llamar al método bajo prueba
    await app.on_chat_input_submitted(event)
    
    # Verificar que el input del widget fue limpiado inmediatamente
    assert event.input.value == ""
    
    # Verificar que run_worker fue llamado para ejecutar el comando de fondo sin bloquear el hilo principal
    app.run_worker.assert_called_once()
    
    # Verificar que no se delegó a on_input_submitted (porque fue interceptado localmente)
    app.on_input_submitted.assert_not_called()

@pytest.mark.anyio
async def test_on_chat_input_submitted_passes_non_config_commands_to_server():
    app = KogniTermTUI.__new__(KogniTermTUI)
    app.command_processor = MagicMock()
    app.run_worker = MagicMock()
    app.on_input_submitted = AsyncMock()
    
    # Crear un evento para un comando no local (por ejemplo, /reset, que debe enviarse al backend)
    event = DummyEvent("/reset")
    
    await app.on_chat_input_submitted(event)
    
    # Verificar que NO se ejecutó como worker local
    app.run_worker.assert_not_called()
    
    # Verificar que se delegó a on_input_submitted
    app.on_input_submitted.assert_called_once_with(event)
