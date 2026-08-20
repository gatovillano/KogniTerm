import pytest
from kogniterm.core.mcp.mcp_manager import MCPManager

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
