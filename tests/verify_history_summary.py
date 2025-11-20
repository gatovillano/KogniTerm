import sys
import os
import json
from typing import List

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kogniterm.core.history_manager import HistoryManager
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

def mock_summarize(messages: List[BaseMessage]) -> str:
    return f"Resumen de {len(messages)} mensajes."

def test_history_summarization():
    history_file = "tests/test_history.json"
    if os.path.exists(history_file):
        os.remove(history_file)

    # Initialize HistoryManager with small limits
    hm = HistoryManager(history_file, max_history_messages=5, max_history_chars=1000)
    
    # Add 10 messages
    for i in range(10):
        hm.add_message(HumanMessage(content=f"Mensaje usuario {i}"))
        hm.add_message(AIMessage(content=f"Respuesta asistente {i}"))

    print(f"Initial history length: {len(hm.get_history())}")
    
    # Process history (should trigger summarization)
    # We pass empty current_llm_messages because we are testing the internal logic of HistoryManager
    # which now uses self.conversation_history directly for length checks.
    processed_history = hm.get_processed_history_for_llm(
        llm_service_summarize_method=mock_summarize,
        max_history_messages=5,
        max_history_chars=1000,
        console=None,
        current_llm_messages=[], 
        save_history=True
    )
    
    print(f"Processed history length: {len(processed_history)}")
    
    # Verify content
    first_msg = processed_history[0]
    print(f"First message type: {type(first_msg)}")
    print(f"First message content: {first_msg.content}")
    
    if isinstance(first_msg, SystemMessage) and "Resumen" in str(first_msg.content):
        print("SUCCESS: Summary message found at the beginning.")
    else:
        print("FAILURE: Summary message not found.")

    # Verify we kept recent messages
    last_msg = processed_history[-1]
    print(f"Last message content: {last_msg.content}")
    if "Respuesta asistente 9" in str(last_msg.content):
        print("SUCCESS: Recent message preserved.")
    else:
        print("FAILURE: Recent message lost.")

    # Clean up
    if os.path.exists(history_file):
        os.remove(history_file)

if __name__ == "__main__":
    test_history_summarization()
