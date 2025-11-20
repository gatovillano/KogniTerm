
import sys
import os
import shutil
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from kogniterm.core.history_manager import HistoryManager
from kogniterm.core.llm_service import LLMService
from kogniterm.core.agent_state import AgentState

# Mock console for HistoryManager
class MockConsole:
    def print(self, *args, **kwargs):
        pass

def verify_fix():
    print("--- Verifying Fix with Real Classes ---")
    
    # Setup temporary history file
    history_file = "temp_history_verify.json"
    if os.path.exists(history_file):
        os.remove(history_file)
        
    # 1. Initialize HistoryManager
    history_manager = HistoryManager(history_file_path=history_file)
    
    # 2. Initialize LLMService (mocking dependencies)
    # We only need it to access history_manager
    llm_service = LLMService()
    llm_service.history_manager = history_manager # Inject our instance
    llm_service.console = MockConsole()
    
    # 3. Initialize AgentState with LLM history
    agent_state = AgentState(messages=llm_service.conversation_history)
    
    print(f"Initial State:")
    print(f"  LLM History ID: {id(llm_service.conversation_history)}")
    print(f"  Agent State ID: {id(agent_state.messages)}")
    print(f"  Same object? {llm_service.conversation_history is agent_state.messages}")
    
    if llm_service.conversation_history is not agent_state.messages:
        print("  [FAIL] Initial references are different!")
        return

    # 4. Add initial message
    human_msg = HumanMessage(content="List files")
    llm_service.conversation_history.append(human_msg)
    
    # 5. Simulate LLM processing (calling get_processed_history_for_llm)
    # This triggered the reference break before
    print("\nCalling get_processed_history_for_llm...")
    processed_history = history_manager.get_processed_history_for_llm(
        llm_service_summarize_method=lambda x: "Summary",
        max_history_messages=10,
        max_history_chars=1000,
        console=MockConsole(),
        save_history=False
    )
    
    print("\nAfter Processing:")
    print(f"  LLM History ID: {id(llm_service.conversation_history)}")
    print(f"  Agent State ID: {id(agent_state.messages)}")
    print(f"  Same object? {llm_service.conversation_history is agent_state.messages}")
    
    if llm_service.conversation_history is not agent_state.messages:
        print("  [FAIL] References have DIVERGED! Fix failed.")
        return
    else:
        print("  [OK] References preserved.")

    # 6. Simulate Agent adding AIMessage
    print("\nAgent appends AIMessage to AgentState...")
    ai_msg = AIMessage(content="I will list files.", tool_calls=[{'name': 'ls', 'args': {}, 'id': 'call_123'}])
    agent_state.messages.append(ai_msg)
    
    # 7. Check if LLM service sees it
    print("Checking LLM Service History:")
    if ai_msg in llm_service.conversation_history:
        print("  [OK] AIMessage is in LLM history.")
    else:
        print("  [FAIL] AIMessage is MISSING from LLM history!")
        return

    # 8. Simulate Tool Execution and adding ToolMessage
    print("\nAdding ToolMessage...")
    tool_msg = ToolMessage(content="file1.txt", tool_call_id='call_123')
    # Usually added to llm_service.conversation_history or agent_state.messages
    # Let's add to agent_state.messages as agent does
    agent_state.messages.append(tool_msg)
    
    # 9. Process again (check for orphan removal)
    print("\nProcessing again (checking for orphan removal)...")
    processed_history_2 = history_manager.get_processed_history_for_llm(
        llm_service_summarize_method=lambda x: "Summary",
        max_history_messages=10,
        max_history_chars=1000,
        console=MockConsole(),
        save_history=False
    )
    
    # Check if ToolMessage is preserved (it should be if AIMessage is present)
    if tool_msg in processed_history_2:
        print("  [OK] ToolMessage preserved (not orphan).")
    else:
        print("  [FAIL] ToolMessage was REMOVED (orphan)!")
        # Debug
        print("  History content:")
        for msg in processed_history_2:
            print(f"    - {type(msg).__name__}: {msg.content}")

    # Cleanup
    if os.path.exists(history_file):
        os.remove(history_file)

if __name__ == "__main__":
    verify_fix()
