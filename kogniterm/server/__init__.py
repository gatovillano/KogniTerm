"""
KogniTerm Server - API Backend persistente multi-canal.

Expone el motor de KogniTerm como un servicio REST + WebSocket,
manteniendo el agente "despierto" y disponible para múltiples canales.
"""
from .app import app, create_app

__all__ = ["app", "create_app"]
