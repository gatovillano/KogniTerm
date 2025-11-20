
import sys
import os
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

# Mock classes to simulate the issue
class MockHistoryManager:
    def __init__(self):
        self.conversation_history: List[BaseMessage] = []

    def process_history(self):
        # Simulate replacing the list object, as seen in HistoryManager.get_processed_history_for_llm
        # self.conversation_history = self._remove_orphan_tool_messages(self.conversation_history)
        print("MockHistoryManager: Processing history and REPLACING list object...")
        new_history = [msg for msg in self.conversation_history] # Create a copy (new object)
        self.conversation_history = new_history # Replace reference

class MockLLMService:
    def __init__(self, history_manager):
        self.history_manager = history_manager

    @property
    def conversation_history(self):
        return self.history_manager.conversation_history

    def invoke(self):
        print("MockLLMService: Invoking...")
        self.history_manager.process_history()
        return AIMessage(content="Response")

class MockAgentState:
    def __init__(self, messages):
        self.messages = messages

def reproduce():
    print("--- Starting Reproduction ---")
    
    # 1. Setup
    history_manager = MockHistoryManager()
    llm_service = MockLLMService(history_manager)
    
    # Initial history
    initial_msg = HumanMessage(content="Hello")
    history_manager.conversation_history.append(initial_msg)
    
    # AgentState shares the reference
    agent_state = MockAgentState(messages=llm_service.conversation_history)
    
    print(f"Initial State:")
    print(f"  LLM History ID: {id(llm_service.conversation_history)}")
    print(f"  Agent State ID: {id(agent_state.messages)}")
    print(f"  Same object? {llm_service.conversation_history is agent_state.messages}")
    
    # 2. Invoke LLM (which processes history and replaces the list in HistoryManager)
    response = llm_service.invoke()
    
    print("\nAfter Invoke (History Processed):")
    print(f"  LLM History ID: {id(llm_service.conversation_history)}")
    print(f"  Agent State ID: {id(agent_state.messages)}")
    print(f"  Same object? {llm_service.conversation_history is agent_state.messages}")
    
    if llm_service.conversation_history is not agent_state.messages:
        print("  [!] References have DIVERGED!")
    
    # 3. Agent appends response to ITS state (stale reference)
    print("\nAgent appends AIMessage to AgentState...")
    agent_state.messages.append(response)
    
    # 4. Check if LLM service sees it
    print("\nChecking LLM Service History:")
    if response in llm_service.conversation_history:
        print("  [OK] Response is in LLM history.")
    else:
        print("  [FAIL] Response is MISSING from LLM history!")
        
    # 5. Simulate KogniTermApp re-sync (overwriting AgentState with LLM history)
    print("\nKogniTermApp re-syncs: agent_state.messages = llm_service.conversation_history")
    agent_state.messages = llm_service.conversation_history
    
    print("Checking AgentState after re-sync:")
    if response in agent_state.messages:
        print("  [OK] Response preserved.")
    else:
        print("  [FAIL] Response LOST permanently!")

if __name__ == "__main__":
    reproduce()
