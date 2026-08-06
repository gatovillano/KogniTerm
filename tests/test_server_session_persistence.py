import pytest
import asyncio
from kogniterm.server.session_pool import ServerUI

def test_agent_session_live_state_buffer():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        ui = ServerUI(loop=loop, session_id="test_sess")
        ui._push("live_update", {"thinking": "Pensando en la solución...", "response": "Procesando respuesta"})
        
        assert ui.current_thinking == "Pensando en la solución..."
        assert ui.current_response == "Procesando respuesta"
        
        ui.reset_live_buffer()
        assert ui.current_thinking == ""
        assert ui.current_response == ""
    finally:
        loop.close()
