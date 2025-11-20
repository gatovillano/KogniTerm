
import sys
import os
from typing import List
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agents.bash_agent import AgentState, call_model_node
from rich.console import Console

# Mock LLMService to avoid actual API calls if possible, or use real one to test model behavior
# For this reproduction, we want to test the *logic* of call_model_node given an empty response
# But we also want to know if the REAL model returns empty response.
# Let's use the real LLMService first.

def reproduce():
    console = Console()
    llm_service = LLMService()
    
    # Construct history matching the user's scenario
    history = [
        SystemMessage(content="Eres KogniTerm..."),
        HumanMessage(content="cual es el puerto que expone el contenedor inmobiliaria-wordpress-1?"),
        AIMessage(content="", tool_calls=[{'name': 'execute_command', 'args': {'command': 'docker inspect inmobiliaria-wordpress-1'}, 'id': 'call_123'}]),
        ToolMessage(content='[{"Id": "123", "State": {"Status": "running"}}]', tool_call_id='call_123')
    ]
    
    state = AgentState()
    state.messages = history
    
    print("Invoking call_model_node with constructed history...")
    
    # We need to mock the generator behavior of llm_service.invoke if we want to test call_model_node logic without API
    # But to test WHY the model returns empty, we need the API.
    
    # Let's try to invoke the real service and see what happens.
    # Note: This requires the API key to be set in environment.
    
    try:
        result = call_model_node(state, llm_service)
        print("\nResult from call_model_node:")
        print(result)
        
        last_msg = state.messages[-1]
        print(f"\nLast message type: {type(last_msg)}")
        print(f"Last message content: '{last_msg.content}'")
        
        if isinstance(last_msg, AIMessage) and not last_msg.content and not last_msg.tool_calls:
            print("\nFAIL: Agent returned empty AIMessage!")
        else:
            print("\nSUCCESS: Agent returned content or tool calls.")
            
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    reproduce()
