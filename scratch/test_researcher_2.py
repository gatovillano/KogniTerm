import sys
import os
import traceback
sys.path.append(os.path.abspath("."))
import logging
logging.basicConfig(level=logging.INFO)

from kogniterm.core.agents.deep_researcher import DeepResearchState, create_deep_researcher
from langchain_core.messages import HumanMessage
from kogniterm.core.llm_service import LLMService

try:
    llm = LLMService(use_multi_provider=False)
    agent_researcher = create_deep_researcher(llm, None, None)
    
    state = DeepResearchState(
        messages=[HumanMessage(content="¿Cómo funciona el universo?")],
        message_manager=None,
        history_manager_ref=None
    )
    
    print("Invocando agente...")
    res = agent_researcher.invoke(state)
    print("Finalizó correctamente:", res)
except Exception as e:
    print(f"EXCEPTION CAUGHT: {e}")
    traceback.print_exc()
