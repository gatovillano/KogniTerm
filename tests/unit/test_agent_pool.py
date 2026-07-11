import pytest
import asyncio
from kogniterm.core.delegation.agent_pool import AgentPool


@pytest.mark.asyncio
async def test_agent_pool_execution():
    pool = AgentPool(max_concurrent=2)

    class DummyGraph:
        def __init__(self, val):
            self.val = val

        async def ainvoke(self, state, config=None):
            await asyncio.sleep(0.05)
            return {"messages": ["done_" + self.val]}

    agents_to_run = [
        {"id": "a1", "graph": DummyGraph("1"), "initial_state": {}, "recursion_limit": 100},
        {"id": "a2", "graph": DummyGraph("2"), "initial_state": {}, "recursion_limit": 100},
    ]

    results = await pool.execute_parallel(agents_to_run)

    assert len(results) == 2
    assert results[0] == {"messages": ["done_1"]}
    assert results[1] == {"messages": ["done_2"]}


@pytest.mark.asyncio
async def test_agent_pool_respects_concurrency_limit():
    """Verifica que el semáforo limita la concurrencia efectiva."""
    max_concurrent = 2
    pool = AgentPool(max_concurrent=max_concurrent)
    concurrent_counter = {"current": 0, "peak": 0}

    class TrackedGraph:
        def __init__(self, delay: float):
            self.delay = delay

        async def ainvoke(self, state, config=None):
            concurrent_counter["current"] += 1
            concurrent_counter["peak"] = max(
                concurrent_counter["peak"], concurrent_counter["current"]
            )
            await asyncio.sleep(self.delay)
            concurrent_counter["current"] -= 1
            return {"done": True}

    agents_to_run = [
        {"id": f"a{i}", "graph": TrackedGraph(0.05), "initial_state": {}, "recursion_limit": 100}
        for i in range(5)
    ]

    results = await pool.execute_parallel(agents_to_run)

    assert len(results) == 5
    assert all(r == {"done": True} for r in results)
    assert concurrent_counter["peak"] <= max_concurrent


@pytest.mark.asyncio
async def test_agent_pool_handles_exceptions():
    """Verifica que las excepciones se propagan como resultados, no se tragan."""
    pool = AgentPool(max_concurrent=2)

    class FailingGraph:
        async def ainvoke(self, state, config=None):
            raise ValueError("Agent failed intentionally")

    class OkGraph:
        async def ainvoke(self, state, config=None):
            return {"done": True}

    agents_to_run = [
        {"id": "ok", "graph": OkGraph(), "initial_state": {}, "recursion_limit": 100},
        {"id": "fail", "graph": FailingGraph(), "initial_state": {}, "recursion_limit": 100},
    ]

    results = await pool.execute_parallel(agents_to_run)

    assert len(results) == 2
    ok_result = next(r for r in results if not isinstance(r, Exception))
    err_result = next(r for r in results if isinstance(r, Exception))
    assert ok_result == {"done": True}
    assert isinstance(err_result, ValueError)


@pytest.mark.asyncio
async def test_agent_pool_cleans_active_tasks_after_execution():
    """Verifica que active_tasks se limpia después de la ejecución."""
    pool = AgentPool(max_concurrent=2)

    class DummyGraph:
        async def ainvoke(self, state, config=None):
            return {}

    agents_to_run = [
        {"id": "a1", "graph": DummyGraph(), "initial_state": {}, "recursion_limit": 100},
    ]

    await pool.execute_parallel(agents_to_run)

    assert len(pool.active_tasks) == 0
