
import sys
import os
from typing import List
from dataclasses import dataclass, field

# Mock classes
@dataclass
class BaseMessage:
    content: str

@dataclass
class AgentState:
    messages: List[BaseMessage] = field(default_factory=list)

class HistoryManager:
    def __init__(self):
        self.conversation_history = []

class LLMService:
    def __init__(self):
        self.history_manager = HistoryManager()
    
    @property
    def conversation_history(self):
        return self.history_manager.conversation_history
    
    @conversation_history.setter
    def conversation_history(self, value):
        self.history_manager.conversation_history = value

# Simulation
def run_simulation():
    llm_service = LLMService()
    agent_state = AgentState()
    
    # Initial sync
    agent_state.messages = llm_service.conversation_history
    
    print(f"Initial: LLM ID={id(llm_service.conversation_history)}, State ID={id(agent_state.messages)}")
    
    # Simulate Agent Loop
    # 1. Agent appends message
    msg = BaseMessage("New Message")
    agent_state.messages.append(msg)
    
    print(f"After Append: LLM has {len(llm_service.conversation_history)} msgs. State has {len(agent_state.messages)} msgs.")
    
    if len(llm_service.conversation_history) != len(agent_state.messages):
        print("FAIL: Lists are not synchronized!")
    else:
        print("OK: Lists are synchronized.")

    # Simulate KogniTermApp overwrite
    # If they are synchronized, this is a no-op (reference assignment)
    agent_state.messages = llm_service.conversation_history
    
    print(f"After Re-sync: State has {len(agent_state.messages)} msgs.")

    # Simulate HistoryManager replacement (The bug I fixed)
    # If HistoryManager replaces the list:
    new_list = [BaseMessage("Old"), BaseMessage("New")]
    llm_service.history_manager.conversation_history = new_list
    
    print(f"After HM Replacement: LLM ID={id(llm_service.conversation_history)}, State ID={id(agent_state.messages)}")
    
    # Now Agent appends again
    agent_state.messages.append(BaseMessage("Another"))
    
    print(f"After 2nd Append: LLM has {len(llm_service.conversation_history)} msgs. State has {len(agent_state.messages)} msgs.")
    
    if len(llm_service.conversation_history) != len(agent_state.messages):
        print("FAIL: Lists diverged!")
    
    # KogniTermApp overwrite
    agent_state.messages = llm_service.conversation_history
    print(f"After 2nd Re-sync: State has {len(agent_state.messages)} msgs. (Should be 2 if diverged and overwritten)")

if __name__ == "__main__":
    run_simulation()
