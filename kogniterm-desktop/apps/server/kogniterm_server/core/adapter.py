import os
import sys
import queue
from typing import List, Generator, Union, Optional

# Add the parent directory (Gemini-Interpreter) to sys.path to find kogniterm
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from kogniterm.core.llm_service import LLMService
from kogniterm.core.command_executor import CommandExecutor
from kogniterm.core.agent_state import AgentState
from kogniterm.core.history_manager import BaseMessage

class KogniTermAdapter:
    def __init__(self, workspace_directory: Optional[str] = None):
        self.workspace_directory = workspace_directory or os.getcwd()
        self.interrupt_queue = queue.Queue()
        
        # Initialize core components
        self.llm_service = LLMService(interrupt_queue=self.interrupt_queue)
        self.command_executor = CommandExecutor()
        self.agent_state = AgentState(messages=self.llm_service.conversation_history)
        
        # Link agent state to tools
        self.llm_service.skill_manager.set_agent_state(self.agent_state)

    def get_chat_history(self) -> List[BaseMessage]:
        return self.llm_service.conversation_history

    async def send_message_stream(self, message: str) -> Generator[Union[str, dict], None, None]:
        # Note: LLMService.invoke returns a generator that yields AIMessage or str
        # We need to handle this in a way that can be streamed to the frontend via WebSocket
        
        # For simplicity in this adapter, we just wrap the existing invoke
        # In a real async environment, we might need to handle the thread-based generator of LLMService
        for chunk in self.llm_service.invoke(history=self.agent_state.messages):
             yield chunk

    def reset_history(self):
        self.llm_service.history_manager.clear_history()
        self.agent_state.messages = []
