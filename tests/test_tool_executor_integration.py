import pytest
import asyncio
from kogniterm.core.agents.tool_executor import ToolExecutor
from kogniterm.core.agents.parallel_tool_dispatcher import ToolCallItem, ParallelToolDispatcher

@pytest.mark.asyncio
async def test_parallel_tool_dispatcher_integration():
    dispatcher = ParallelToolDispatcher()
    calls = [
        ToolCallItem(id="c1", name="read_file", args={"path": "a.txt"}),
        ToolCallItem(id="c2", name="read_file", args={"path": "b.txt"})
    ]
    
    async def mock_exec(args):
        return f"content of {args['path']}"

    results = await dispatcher.execute_batch(calls, {"read_file": mock_exec})
    assert len(results) == 2
    assert results[0].output == "content of a.txt"
    assert results[1].output == "content of b.txt"
