
import os
import sys
from typing import Any, List, Optional
from langchain_core.messages import HumanMessage
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.deep_coder import create_deep_coder
from kogniterm.core.agents.deep_researcher import create_deep_researcher

def test_agents():
    llm_service = LLMService()
    
    print("Testing DeepCoder creation...")
    try:
        agent_coder = create_deep_coder(llm_service)
        print("DeepCoder created successfully.")
    except Exception as e:
        print(f"Error creating DeepCoder: {e}")
        return

    print("Testing DeepResearcher creation...")
    try:
        agent_researcher = create_deep_researcher(llm_service)
        print("DeepResearcher created successfully.")
    except Exception as e:
        print(f"Error creating DeepResearcher: {e}")
        return

    print("All agents created successfully.")

if __name__ == "__main__":
    test_agents()
