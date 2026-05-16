import os
from kogniterm.core.session_manager import SessionManager

class SessionService:
    def __init__(self, llm_service):
        self.llm_service = llm_service
        self.session_manager = SessionManager(llm_service)

    def list_sessions(self):
        return self.session_manager.list_sessions()

    def save_session(self, name: str):
        return self.session_manager.save_session(name)

    def load_session(self, name: str):
        return self.session_manager.load_session(name)
