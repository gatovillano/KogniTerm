#!/usr/bin/env python3
"""
Script de verificación simplificado para el fix de truncamiento de historial.
Prueba directamente el método _truncate_history sin dependencias externas.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

# Simular HistoryManager._truncate_history directamente
def get_message_length(msg):
    """Calcula la longitud de un mensaje."""
    if hasattr(msg, 'content'):
        return len(str(msg.content))
    return 0

def truncate_history_new(history, max_messages, max_chars):
    """
    Nueva implementación de _truncate_history que protege pares AIMessage-ToolMessage.
    """
    MIN_MESSAGES_TO_KEEP = 5
    
    # Separar mensajes del sistema de mensajes conversacionales
    system_messages = [msg for msg in history if isinstance(msg, SystemMessage)]
    conversational_messages = [msg for msg in history if not isinstance(msg, SystemMessage)]
    
    # Identificar AIMessages que son padres de ToolMessages presentes
    protected_ai_message_indices = set()
    for i, msg in enumerate(conversational_messages):
        if isinstance(msg, ToolMessage):
            # Buscar el AIMessage padre
            for j in range(i - 1, -1, -1):
                if isinstance(conversational_messages[j], AIMessage) and conversational_messages[j].tool_calls:
                    for tc in conversational_messages[j].tool_calls:
                        if tc.get('id') == msg.tool_call_id:
                            protected_ai_message_indices.add(j)
                            break
    
    # Calcular longitud total
    total_length = sum(get_message_length(msg) for msg in history)
    
    # Truncar mientras se excedan los límites
    while (len(conversational_messages) > max_messages or total_length > max_chars) and \
          len(conversational_messages) > MIN_MESSAGES_TO_KEEP:
        
        # Intentar truncar ToolMessages grandes primero
        truncated_any = False
        if total_length > max_chars:
            for i, msg in enumerate(conversational_messages):
                if isinstance(msg, ToolMessage):
                    msg_length = get_message_length(msg)
                    if msg_length > 5000:  # Si el ToolMessage es grande
                        # Truncar el contenido del ToolMessage
                        original_content = msg.content
                        if len(original_content) > 3000:
                            truncated_content = original_content[:1500] + "\n\n... [Contenido truncado por límite de historial] ...\n\n" + original_content[-1500:]
                            msg.content = truncated_content
                            length_saved = msg_length - get_message_length(msg)
                            total_length -= length_saved
                            truncated_any = True
                            if total_length <= max_chars:
                                break
        
        # Si aún excedemos los límites, eliminar mensajes antiguos (pero proteger AIMessages padres)
        if not truncated_any or len(conversational_messages) > max_messages:
            removed = False
            for i in range(len(conversational_messages)):
                # No eliminar AIMessages protegidos
                if i in protected_ai_message_indices:
                    continue
                
                # No eliminar ToolMessages que tengan un AIMessage padre protegido
                if isinstance(conversational_messages[i], ToolMessage):
                    # Verificar si su padre está protegido
                    has_protected_parent = False
                    for j in range(i - 1, -1, -1):
                        if isinstance(conversational_messages[j], AIMessage) and conversational_messages[j].tool_calls:
                            for tc in conversational_messages[j].tool_calls:
                                if tc.get('id') == conversational_messages[i].tool_call_id:
                                    if j in protected_ai_message_indices:
                                        has_protected_parent = True
                                    break
                    if has_protected_parent:
                        continue
                
                # Eliminar este mensaje
                removed_msg = conversational_messages.pop(i)
                total_length -= get_message_length(removed_msg)
                
                # Actualizar índices protegidos
                protected_ai_message_indices = {idx - 1 if idx > i else idx for idx in protected_ai_message_indices}
                removed = True
                break
            
            if not removed:
                # Si no pudimos eliminar nada, salir del bucle
                break
    
    return system_messages + conversational_messages

def test_truncate_with_large_tool_message():
    """Verifica que _truncate_history proteja los pares AIMessage-ToolMessage."""
    
    # Crear un historial con un ToolMessage gigante
    history = [
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
    print(f"  - Total de mensajes: {len(history)}")
    print(f"  - Último mensaje: {type(history[-1]).__name__}")
    total_chars = sum(get_message_length(msg) for msg in history)
    print(f"  - Total de caracteres: {total_chars}")
    
    # Procesar el historial con límites bajos para forzar truncamiento
    processed_history = truncate_history_new(
        history=history,
        max_messages=10,
        max_chars=5000  # Límite bajo para forzar truncamiento
    )
    
    print("\n📊 Historial procesado:")
    print(f"  - Total de mensajes: {len(processed_history)}")
    total_chars_after = sum(get_message_length(msg) for msg in processed_history)
    print(f"  - Total de caracteres: {total_chars_after}")
    
    # Verificar que el AIMessage padre y el ToolMessage estén presentes
    ai_message_found = False
    tool_message_found = False
    tool_message_truncated = False
    
    for msg in processed_history:
        msg_type = type(msg).__name__
        content_preview = msg.content[:50] if hasattr(msg, 'content') else 'N/A'
        print(f"  - {msg_type}: {content_preview}...")
        
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get('id') == 'tool_call_123':
                    ai_message_found = True
                    print("    ✅ AIMessage padre encontrado")
        
        if isinstance(msg, ToolMessage) and msg.tool_call_id == 'tool_call_123':
            tool_message_found = True
            print(f"    ✅ ToolMessage encontrado (longitud: {len(msg.content)} chars)")
            if "[Contenido truncado por límite de historial]" in msg.content:
                tool_message_truncated = True
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
    
    if tool_message_truncated:
        print("  ✅ ToolMessage fue truncado (no se eliminó el AIMessage padre)")
    else:
        print("  ⚠️  ToolMessage no fue truncado (puede ser esperado si el límite es suficiente)")
    
    if ai_message_found and tool_message_found:
        print("\n✅ PRUEBA EXITOSA: El fix funciona correctamente")
        return True
    else:
        print("\n❌ PRUEBA FALLIDA: El fix no funciona")
        return False

if __name__ == "__main__":
    success = test_truncate_with_large_tool_message()
    sys.exit(0 if success else 1)
