import pytest
from unittest.mock import MagicMock, PropertyMock, patch
from textual import events
from kogniterm.terminal.tui.tui_app import KogniTermTUI, TerminalPanel


def test_interactive_key_mapping():
    """Verifica que en modo interactivo las teclas de navegación (flechas, enter, espacio, tab) se envíen al PTY."""
    app = KogniTermTUI()
    
    mock_executor = MagicMock()
    app.interactive_executor = mock_executor
    app._cursor_active = True
    
    panel = TerminalPanel()
    
    with patch.object(KogniTermTUI, "focused", new_callable=PropertyMock) as mock_focused:
        mock_focused.return_value = panel
        
        # Probar tecla 'up'
        event_up = events.Key(key="up", character=None)
        event_up.prevent_default = MagicMock()
        app.on_key(event_up)
        
        mock_executor.write_input.assert_called_with("\x1b[A")
        event_up.prevent_default.assert_called_once()
        
        # Probar tecla 'down'
        event_down = events.Key(key="down", character=None)
        event_down.prevent_default = MagicMock()
        app.on_key(event_down)
        
        mock_executor.write_input.assert_called_with("\x1b[B")
        event_down.prevent_default.assert_called_once()
        
        # Probar tecla 'enter'
        event_enter = events.Key(key="enter", character=None)
        event_enter.prevent_default = MagicMock()
        app.on_key(event_enter)
        
        mock_executor.write_input.assert_called_with("\r")
        event_enter.prevent_default.assert_called_once()
        
        # Probar tecla 'space'
        event_space = events.Key(key="space", character=" ")
        event_space.prevent_default = MagicMock()
        app.on_key(event_space)
        
        mock_executor.write_input.assert_called_with(" ")
        event_space.prevent_default.assert_called_once()
