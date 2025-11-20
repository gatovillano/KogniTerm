import sys
import os
from typing import List, Dict, Any, Set
from dataclasses import dataclass

# Mocks mínimos para simular las clases de LangChain
@dataclass
class BaseMessage:
    content: str
    type: str

@dataclass
class AIMessage(BaseMessage):
    tool_calls: List[Dict[str, Any]] = None
    type: str = "ai"

@dataclass
class ToolMessage(BaseMessage):
    tool_call_id: str = None
    type: str = "tool"

@dataclass
class HumanMessage(BaseMessage):
    type: str = "human"

# Versión simplificada de la lógica de HistoryManager._remove_orphan_tool_messages
def remove_orphan_tool_messages(history: List[BaseMessage]) -> List[BaseMessage]:
    # Recopilar todos los tool_call_ids válidos
    valid_tool_call_ids: Set[str] = set()
    for msg in history:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if 'id' in tc and tc['id']:
                    valid_tool_call_ids.add(tc['id'])
    
    print(f"DEBUG: IDs válidos encontrados: {valid_tool_call_ids}")

    # Filtrar mensajes
    filtered_history = []
    for i, msg in enumerate(history):
        if isinstance(msg, ToolMessage):
            # Omitir ToolMessages sin AIMessage correspondiente
            if not msg.tool_call_id:
                    if i > 0 and isinstance(history[i-1], AIMessage) and history[i-1].tool_calls:
                        filtered_history.append(msg)
                        continue
            
            if msg.tool_call_id and msg.tool_call_id not in valid_tool_call_ids:
                # LÓGICA CORREGIDA: Verificar si el mensaje anterior es un AIMessage con tool_calls
                if i > 0 and isinstance(history[i-1], AIMessage) and history[i-1].tool_calls:
                     print(f"DEBUG: ToolMessage huérfano aceptado por contexto implícito. ID: {msg.tool_call_id}")
                     filtered_history.append(msg)
                     continue

                print(f"DEBUG: Eliminando ToolMessage huérfano. ID: {msg.tool_call_id}")
                continue
        filtered_history.append(msg)
    
    return filtered_history

def test_reproduction():
    print("🧪 Iniciando reproducción del problema de historial...")

    # Caso 1: AIMessage con ID None, ToolMessage con ID generado
    print("\nCaso 1: AIMessage con ID None, ToolMessage con ID generado")
    history1 = [
        HumanMessage(content="ejecuta algo"),
        AIMessage(content="voy a ejecutar", tool_calls=[{'name': 'exec', 'args': {}, 'id': None}]),
        ToolMessage(content="resultado", tool_call_id="generated-uuid-123")
    ]
    
    processed1 = remove_orphan_tool_messages(history1)
    if len(processed1) == 3:
        print("✅ Caso 1: ToolMessage preservado (Inesperado si el bug existe)")
    else:
        print("❌ Caso 1: ToolMessage ELIMINADO (Bug reproducido)")

    # Caso 2: AIMessage con ID correcto, ToolMessage con ID correcto
    print("\nCaso 2: AIMessage con ID correcto, ToolMessage con ID correcto")
    history2 = [
        HumanMessage(content="ejecuta algo"),
        AIMessage(content="voy a ejecutar", tool_calls=[{'name': 'exec', 'args': {}, 'id': 'correct-id'}]),
        ToolMessage(content="resultado", tool_call_id="correct-id")
    ]
    
    processed2 = remove_orphan_tool_messages(history2)
    if len(processed2) == 3:
        print("✅ Caso 2: ToolMessage preservado (Comportamiento correcto)")
    else:
        print("❌ Caso 2: ToolMessage ELIMINADO (Error en lógica base)")

if __name__ == "__main__":
    test_reproduction()
