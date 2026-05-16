import sys
import os
sys.path.append(os.path.abspath("."))
import logging
logging.basicConfig(level=logging.DEBUG)

from kogniterm.core.agents.deep_researcher import DeepResearchState
from langchain_core.messages import HumanMessage

try:
    state = DeepResearchState(
        messages=[HumanMessage(content="Test")],
        message_manager=None,
        history_manager_ref=None
    )
    print("State created successfully.")
except Exception as e:
    print(f"Exception creating state: {type(e)}: {e}")

try:
    from kogniterm.core.llm_service import LLMService
    from kogniterm.core.agents.deep_researcher import create_deep_researcher
    llm = LLMService(use_multi_provider=False)
    agent_researcher = create_deep_researcher(llm, None, None)
    print("Agent created.")
    res = agent_researcher.invoke(state)
    print("Agent invoked.")
except Exception as e:
    print(f"Exception invoking agent: {type(e)}: {e}")
