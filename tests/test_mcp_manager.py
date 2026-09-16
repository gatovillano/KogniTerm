import pytest
import sys
import threading
from unittest.mock import MagicMock
from concurrent.futures import ThreadPoolExecutor
from kogniterm.core.mcp.mcp_manager import MCPManager
from kogniterm.core.llm_service import LLMService

try:
    import mcp.server.fastmcp
    _HAS_FASTMCP = True
except ImportError:
    _HAS_FASTMCP = False

_FASTMCP_SERVER_SCRIPT = """
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('test_calc')
@mcp.tool()
def multiply(x: int, y: int) -> int:
    return x * y
if __name__ == '__main__':
    mcp.run()
"""

@pytest.mark.asyncio
async def test_mcp_manager_singleton_and_test_connection():
    manager = MCPManager.get_instance()
    assert manager is not None
    
    # Test connection sin comando (error)
    res_err = await manager.test_connection({"transport": "stdio"})
    assert res_err["status"] == "error"
    
    # Test connection sse sin url (error)
    res_sse_err = await manager.test_connection({"transport": "sse"})
    assert res_sse_err["status"] == "error"

    # Test status retrieval
    statuses = manager.get_all_servers_status()
    assert isinstance(statuses, dict)

@pytest.mark.asyncio
@pytest.mark.skipif(not _HAS_FASTMCP, reason="mcp.server.fastmcp not installed")
async def test_mcp_manager_fastmcp_lifecycle_and_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(MCPManager, "_instance", None)
    manager = MCPManager.get_instance()
    
    server_conf = {
        "transport": "stdio",
        "command": sys.executable,
        "args": ["-c", _FASTMCP_SERVER_SCRIPT],
        "disabled": False
    }

    # Probar test_connection
    test_res = await manager.test_connection(server_conf)
    assert test_res["status"] == "ok"
    assert "multiply" in test_res["tools"]

    # Guardar en config_manager y recargar
    manager.config_manager.set_mcp_server("calc_srv", server_conf, scope="project")

    callback_called = []
    manager.register_on_reload_callback(lambda: callback_called.append(True))

    await manager.reload()
    assert len(callback_called) == 1
    assert len(manager.active_tools) > 0
    
    tool = manager.active_tools[0]
    assert tool.name == "multiply"

    # Verificar que LLMService.get_tool resuelve la herramienta
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.skill_manager = MagicMock()
    mock_llm.skill_manager.get_tool.return_value = None
    mock_llm.tool_executor = ThreadPoolExecutor(max_workers=1)
    mock_llm.interrupt_queue = None
    mock_llm.tool_poll_timeout = 0.1
    mock_llm.tool_execution_lock = threading.Lock()
    mock_llm.active_tool_futures = []

    resolved = LLMService.get_tool(mock_llm, "multiply")
    assert resolved is not None

    # Invocar a través del pipeline de LLMService
    gen = LLMService._invoke_tool_with_interrupt(mock_llm, resolved, {"x": 8, "y": 9})
    outputs = list(gen)
    assert any("72" in str(out) for out in outputs)

    # Limpieza
    manager.config_manager.delete_mcp_server("calc_srv", scope="project")
    mock_llm.tool_executor.shutdown(wait=False)
