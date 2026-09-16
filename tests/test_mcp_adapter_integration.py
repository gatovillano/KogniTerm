import pytest
from unittest.mock import MagicMock
from langchain_core.tools import tool
from kogniterm.core.mcp.mcp_manager import MCPManager
from kogniterm.core.ai_cli_bridge.tool_registry_adapter import ToolRegistryAdapter


@tool
def bitwig_mock_tool(track_name: str, volume: float = 0.8) -> str:
    """Ajusta el volumen de un track en Bitwig."""
    return f"Track '{track_name}' volumen ajustado a {volume}"


@pytest.mark.asyncio
async def test_tool_registry_adapter_includes_and_executes_mcp_tools(monkeypatch):
    monkeypatch.setattr(MCPManager, "_instance", None)
    manager = MCPManager.get_instance()
    
    # Asignar herramienta simulada en active_tools de MCPManager
    manager.active_tools = [bitwig_mock_tool]
    
    # Instanciar el adaptador
    adapter = ToolRegistryAdapter()
    
    # 1. Comprobar que get_schemas_for_litellm incluye la herramienta MCP
    schemas = adapter.get_schemas_for_litellm()
    tool_names = [s.get("function", {}).get("name") for s in schemas]
    assert "bitwig_mock_tool" in tool_names
    
    # 2. Comprobar que get_handler resuelve la herramienta MCP
    handler = adapter.get_handler("bitwig_mock_tool")
    assert handler is not None
    assert getattr(handler, "name", "") == "bitwig_mock_tool"
    
    # 3. Comprobar que execute ejecuta la herramienta asíncronamente
    res = await adapter.execute("bitwig_mock_tool", {"track_name": "Audio 1", "volume": 0.5})
    assert "Audio 1" in str(res)
    assert "0.5" in str(res)


@pytest.mark.asyncio
async def test_mcp_manager_get_tool():
    manager = MCPManager.get_instance()
    manager.active_tools = [bitwig_mock_tool]
    
    # Búsqueda exacta
    t1 = manager.get_tool("bitwig_mock_tool")
    assert t1 is not None
    assert t1.name == "bitwig_mock_tool"
    
    # Búsqueda inexistente
    t2 = manager.get_tool("non_existent_tool")
    assert t2 is None
