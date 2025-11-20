#!/usr/bin/env python3
"""
Script de prueba para verificar que el agente recibe correctamente
la salida del comando ejecutado.

Este script simula el flujo de ejecución de un comando y verifica
que el ToolMessage con la salida se preserve en el historial.
"""

import sys
import os

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from kogniterm.core.agent_state import AgentState
from kogniterm.core.llm_service import LLMService

def test_tool_message_preservation():
    """
    Prueba que el ToolMessage se preserve correctamente en el historial
    después de la ejecución de un comando.
    """
    print("🧪 Iniciando prueba de preservación de ToolMessage...")
    
    # Crear instancia de LLMService
    llm_service = LLMService()
    
    # Crear AgentState con la misma referencia que llm_service.conversation_history
    agent_state = AgentState(messages=llm_service.conversation_history)
    
    # Simular el flujo de ejecución
    print("\n1️⃣ Añadiendo mensaje del usuario...")
    user_message = HumanMessage(content="cuanto espacio tengo en el disco root?")
    agent_state.messages.append(user_message)
    llm_service.conversation_history.append(user_message)
    
    print(f"   Historial actual: {len(agent_state.messages)} mensajes")
    print(f"   ¿Son la misma lista? {agent_state.messages is llm_service.conversation_history}")
    
    # Simular respuesta del agente con tool_call
    print("\n2️⃣ Añadiendo respuesta del agente con tool_call...")
    ai_message = AIMessage(
        content="Voy a ejecutar df -h /",
        tool_calls=[{
            'id': 'test_tool_call_123',
            'name': 'execute_command',
            'args': {'command': 'df -h /'}
        }]
    )
    agent_state.messages.append(ai_message)
    
    print(f"   Historial actual: {len(agent_state.messages)} mensajes")
    
    # Simular la ejecución del comando y añadir ToolMessage
    print("\n3️⃣ Añadiendo ToolMessage con la salida del comando...")
    tool_message = ToolMessage(
        content="Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1       100G   50G   50G  50% /",
        tool_call_id='test_tool_call_123'
    )
    agent_state.messages.append(tool_message)
    
    print(f"   Historial actual: {len(agent_state.messages)} mensajes")
    print(f"   Último mensaje: {type(agent_state.messages[-1]).__name__}")
    print(f"   Contenido: {agent_state.messages[-1].content[:50]}...")
    
    # Verificar que el ToolMessage esté en el historial
    print("\n4️⃣ Verificando que el ToolMessage esté en el historial...")
    
    # Verificar en agent_state.messages
    tool_messages_in_agent_state = [msg for msg in agent_state.messages if isinstance(msg, ToolMessage)]
    print(f"   ToolMessages en agent_state: {len(tool_messages_in_agent_state)}")
    
    # Verificar en llm_service.conversation_history
    tool_messages_in_llm_service = [msg for msg in llm_service.conversation_history if isinstance(msg, ToolMessage)]
    print(f"   ToolMessages en llm_service: {len(tool_messages_in_llm_service)}")
    
    # Verificar que sean la misma lista
    print(f"   ¿Son la misma lista? {agent_state.messages is llm_service.conversation_history}")
    
    # Resultado de la prueba
    if len(tool_messages_in_agent_state) == 1 and len(tool_messages_in_llm_service) == 1:
        print("\n✅ PRUEBA EXITOSA: El ToolMessage se preservó correctamente en ambos historiales")
        return True
    else:
        print("\n❌ PRUEBA FALLIDA: El ToolMessage no se preservó correctamente")
        return False

if __name__ == "__main__":
    success = test_tool_message_preservation()
    sys.exit(0 if success else 1)
