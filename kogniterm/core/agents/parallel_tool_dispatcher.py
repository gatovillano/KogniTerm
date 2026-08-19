import asyncio
import inspect
from typing import List, Dict, Any, Callable
from dataclasses import dataclass

READ_ONLY_TOOLS = {
    "read_file", "view_file", "list_dir", "grep_search", "search_web", 
    "read_url_content", "get_file_info", "read_resource"
}

@dataclass
class ToolCallItem:
    id: str
    name: str
    args: Dict[str, Any]

@dataclass
class ToolResult:
    call_id: str
    name: str
    output: Any
    error: bool = False

class ParallelToolDispatcher:
    """Dispatches tool calls concurrently for read-only ops and sequentially for stateful ops."""

    def __init__(self, read_only_tools: set = READ_ONLY_TOOLS):
        self.read_only_tools = read_only_tools

    def is_read_only(self, tool_name: str) -> bool:
        return tool_name in self.read_only_tools

    async def _execute_single(self, item: ToolCallItem, executor: Callable) -> ToolResult:
        try:
            if inspect.iscoroutinefunction(executor):
                res = await executor(item.args)
            else:
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(None, executor, item.args)
            return ToolResult(call_id=item.id, name=item.name, output=res, error=False)
        except Exception as e:
            return ToolResult(call_id=item.id, name=item.name, output=str(e), error=True)

    async def execute_batch(self, tool_calls: List[ToolCallItem], executors: Dict[str, Callable]) -> List[ToolResult]:
        results: Dict[str, ToolResult] = {}
        
        i = 0
        n = len(tool_calls)
        while i < n:
            item = tool_calls[i]
            executor = executors.get(item.name)
            if not executor:
                results[item.id] = ToolResult(
                    call_id=item.id, name=item.name, output=f"Unknown tool: {item.name}", error=True
                )
                i += 1
                continue

            if self.is_read_only(item.name):
                parallel_batch = []
                while i < n and self.is_read_only(tool_calls[i].name) and tool_calls[i].name in executors:
                    parallel_batch.append(tool_calls[i])
                    i += 1
                
                tasks = [self._execute_single(call, executors[call.name]) for call in parallel_batch]
                batch_results = await asyncio.gather(*tasks)
                for res in batch_results:
                    results[res.call_id] = res
            else:
                res = await self._execute_single(item, executor)
                results[res.call_id] = res
                i += 1

        return [results[item.id] for item in tool_calls if item.id in results]
