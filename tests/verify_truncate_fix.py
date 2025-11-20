#!/usr/bin/env python3
"""
Script de verificación para el fix de truncamiento de historial.
Simula un ToolMessage gigante y verifica que el AIMessage padre se conserve.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kogniterm.core.history_manager import HistoryManager
from kogniterm.core.llm_service import LLMService
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

def test_truncate_with_large_tool_message():
    """Verifica que _truncate_history proteja los pares AIMessage-ToolMessage."""
    
    # Crear instancias
    llm_service = LLMService(workspace_id="test_workspace")
    history_manager = HistoryManager(workspace_id="test_workspace")
    
    # Limpiar historial
    history_manager.conversation_history = []
    
    # Crear un historial con un ToolMessage gigante
    history_manager.conversation_history = [
        SystemMessage(content="Sistema inicial"),
        HumanMessage(content="Usuario: Hola"),
        AIMessage(content="Asistente: Hola, ¿cómo estás?"),
        HumanMessage(content="Usuario: Ejecuta docker ps -a"),
        AIMessage(
            content="Voy a ejecutar docker ps -a",
            tool_calls=[{
                'id': 'tool_call_123',
                'name': 'execute_command',
                'args': {'command': 'docker ps -a'}
            }]
        ),
        ToolMessage(
            content="CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS   PORTS   NAMES\n" * 1000,  # Salida gigante
            tool_call_id='tool_call_123'
        ),
    ]
    
    print("📊 Historial inicial:")
    print(f"  - Total de mensajes: {len(history_manager.conversation_history)}")
    print(f"  - Último mensaje: {type(history_manager.conversation_history[-1]).__name__}")
    
    # Procesar el historial con límites bajos para forzar truncamiento
    processed_history = history_manager.get_processed_history_for_llm(
        llm_service_summarize_method=llm_service.summarize_conversation_history,
        max_history_messages=10,
        max_history_chars=5000,  # Límite bajo para forzar truncamiento
        console=None,
        current_llm_messages=[],
        save_history=False
    )
    
    print("\n📊 Historial procesado:")
    print(f"  - Total de mensajes: {len(processed_history)}")
    
    # Verificar que el AIMessage padre y el ToolMessage estén presentes
    ai_message_found = False
    tool_message_found = False
    
    for msg in processed_history:
        print(f"  - {type(msg).__name__}: {msg.content[:50] if hasattr(msg, 'content') else 'N/A'}...")
        
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get('id') == 'tool_call_123':
                    ai_message_found = True
                    print("    ✅ AIMessage padre encontrado")
        
        if isinstance(msg, ToolMessage) and msg.tool_call_id == 'tool_call_123':
            tool_message_found = True
            print(f"    ✅ ToolMessage encontrado (longitud: {len(msg.content)} chars)")
            if "[Contenido truncado por límite de historial]" in msg.content:
                print("    ✅ Contenido del ToolMessage fue truncado correctamente")
    
    # Verificar resultados
    print("\n🔍 Resultados de la verificación:")
    if ai_message_found:
        print("  ✅ AIMessage padre se conservó")
    else:
        print("  ❌ AIMessage padre fue eliminado (BUG!)")
    
    if tool_message_found:
        print("  ✅ ToolMessage se conservó")
    else:
        print("  ❌ ToolMessage fue eliminado (BUG!)")
    
    if ai_message_found and tool_message_found:
        print("\n✅ PRUEBA EXITOSA: El fix funciona correctamente")
        return True
    else:
        print("\n❌ PRUEBA FALLIDA: El fix no funciona")
        return False

if __name__ == "__main__":
    success = test_truncate_with_large_tool_message()
    sys.exit(0 if success else 1)
