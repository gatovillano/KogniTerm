import sys
import os
sys.path.append(os.path.abspath("."))
import logging
logging.basicConfig(level=logging.DEBUG)

from kogniterm.skills.bundled.call_agents_parallel.scripts.tool import call_agents_parallel
from kogniterm.core.llm_service import LLMService

llm = LLMService(use_multi_provider=False)
try:
    gen = llm._invoke_tool_with_interrupt(call_agents_parallel, {"task_coder": "echo hello", "task_researcher": "echo hi"})
    for x in gen:
        print(x)
except Exception as e:
    print(f"Exception: {type(e)}: {e}")
