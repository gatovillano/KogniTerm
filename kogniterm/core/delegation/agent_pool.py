import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class AgentPool:
    """
    Administra la ejecución paralela y asíncrona de múltiples subagentes.
    Encapsula el paralelismo verdadero usando asyncio.Semaphore.
    """

    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_tasks: Dict[str, asyncio.Task] = {}

    async def execute_agent(
        self,
        agent_id: str,
        agent_graph: Any,
        initial_state: Any,
        recursion_limit: int,
    ) -> Any:
        async with self.semaphore:
            logger.info(f"AgentPool: Iniciando ejecución de subagente {agent_id}")
            try:
                return await agent_graph.ainvoke(
                    initial_state,
                    config={"recursion_limit": recursion_limit},
                )
            except Exception as e:
                logger.exception(f"AgentPool: Error en subagente {agent_id}: {e}")
                raise

    async def execute_parallel(
        self, agents_to_run: List[Dict[str, Any]]
    ) -> List[Any]:
        tasks = []
        for spec in agents_to_run:
            agent_id = spec["id"]
            graph = spec["graph"]
            initial_state = spec["initial_state"]
            limit = spec.get("recursion_limit", 1000)

            task = asyncio.create_task(
                self.execute_agent(agent_id, graph, initial_state, limit)
            )
            self.active_tasks[agent_id] = task
            tasks.append(task)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return list(results)
        finally:
            for spec in agents_to_run:
                self.active_tasks.pop(spec["id"], None)
