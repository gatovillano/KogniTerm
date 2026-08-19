import pytest
import asyncio
import time
from kogniterm.core.agents.parallel_tool_dispatcher import ParallelToolDispatcher, ToolCallItem

@pytest.mark.asyncio
async def test_parallel_tool_execution_speed():
    dispatcher = ParallelToolDispatcher()
    
    async def mock_read_file(args):
        await asyncio.sleep(0.1)
        return f"read:{args['path']}"
    
    async def mock_write_file(args):
        await asyncio.sleep(0.1)
        return f"write:{args['path']}"
    
    tool_calls = [
        ToolCallItem(id="1", name="read_file", args={"path": "a.py"}),
        ToolCallItem(id="2", name="read_file", args={"path": "b.py"}),
        ToolCallItem(id="3", name="read_file", args={"path": "c.py"}),
        ToolCallItem(id="4", name="write_to_file", args={"path": "d.py"}),
    ]
    
    executors = {
        "read_file": mock_read_file,
        "write_to_file": mock_write_file,
    }
    
    start = time.time()
    results = await dispatcher.execute_batch(tool_calls, executors)
    elapsed = time.time() - start
    
    # 3 reads in parallel (0.1s total) + 1 write serial (0.1s) -> total ~0.2s, not 0.4s
    assert elapsed < 0.3
    assert len(results) == 4
    assert results[0].output == "read:a.py"
    assert results[1].output == "read:b.py"
    assert results[2].output == "read:c.py"
    assert results[3].output == "write:d.py"
