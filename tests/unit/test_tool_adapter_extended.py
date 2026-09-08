import pytest
from unittest.mock import MagicMock, AsyncMock
from kogniterm.core.ai_cli_bridge.tool_registry_adapter import ToolRegistryAdapter

@pytest.mark.asyncio
async def test_tool_registry_adapter_executes_registered_tool():
    adapter = ToolRegistryAdapter()
    result = await adapter.execute("read_file", {"path": "pyproject.toml", "limit": 1})
    assert isinstance(result, str) or isinstance(result, dict)

@pytest.mark.asyncio
async def test_tool_registry_adapter_unregistered_raises_key_error():
    adapter = ToolRegistryAdapter()
    with pytest.raises(KeyError):
        await adapter.execute("herramienta_inexistente_12345", {})

@pytest.mark.asyncio
async def test_tool_registry_adapter_custom_handler():
    adapter = ToolRegistryAdapter()
    custom_schema = {
        "type": "function",
        "function": {
            "name": "custom_echo",
            "description": "Echo custom",
            "parameters": {"type": "object", "properties": {"msg": {"type": "string"}}}
        }
    }
    adapter.register_handler("custom_echo", lambda msg: f"echo: {msg}", schema=custom_schema)

    schemas = adapter.get_schemas_for_litellm()
    assert any(s["function"]["name"] == "custom_echo" for s in schemas)

    res = await adapter.execute("custom_echo", {"msg": "hello"})
    assert res == "echo: hello"
