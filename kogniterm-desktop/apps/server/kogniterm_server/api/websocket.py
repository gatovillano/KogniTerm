from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ..core.adapter import KogniTermAdapter

router = APIRouter()
adapter = KogniTermAdapter()
executor = ThreadPoolExecutor(max_workers=5)

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            msg_type = message_data.get("type", "chat") # Detectar tipo

            # Manejo de Comandos
            if msg_type == "command":
                if user_message == "reset":
                    adapter.reset()
                    await websocket.send_json({"type": "info", "content": "🔄 Sesión reiniciada."})
                continue

            # Manejo de Meta-Comandos (comenzando con / o %)
            if user_message.startswith("/") or user_message.startswith("%"):
                cmd = user_message.split(" ")[0].lower().replace("/", "").replace("%", "")
                args = user_message.split(" ")[1:]
                
                if cmd == "reset":
                    adapter.agent_state.reset()
                    # Re-initialize history
                    from kogniterm.core.agents.bash_agent import SYSTEM_MESSAGE
                    adapter.llm_service.conversation_history = [SYSTEM_MESSAGE]
                    adapter.llm_service._save_history([SYSTEM_MESSAGE])
                    adapter.agent_state.messages = [SYSTEM_MESSAGE]
                    
                    await websocket.send_json({"type": "info", "content": "🔄 Sesión reiniciada correctamente."})
                    continue

                elif cmd == "undo":
                    if len(adapter.agent_state.messages) >= 3:
                        adapter.agent_state.messages.pop() # Remove AI response
                        adapter.agent_state.messages.pop() # Remove User message
                        await websocket.send_json({"type": "info", "content": "↩️ Última interacción deshecha."})
                    else:
                        await websocket.send_json({"type": "error", "content": "⚠️ No hay nada que deshacer."})
                    continue

                elif cmd == "help":
                    help_text = """### 🛠️ Comandos Disponibles

| Comando | Descripción |
| :--- | :--- |
| `%reset` | Reiniciar conversación y memoria |
| `%undo` | Deshacer la última interacción |
| `%models` | Ver modelo actual y cambiarlo (`%models <nombre>`) |
| `%compress` | Resumir el historial de conversación |
| `%init <files>` | Cargar contexto de archivos específicos |
| `%session save <name>` | Guardar la sesión actual |
| `%session load <name>` | Cargar una sesión guardada |
"""
                    await websocket.send_json({"type": "chunk", "content": help_text})
                    await websocket.send_json({"type": "done"})
                    continue

                elif cmd == "models":
                    if args:
                         new_model = args[0]
                         try:
                             adapter.llm_service.set_model(new_model)
                             await websocket.send_json({"type": "info", "content": f"✅ Modelo cambiado a: {new_model}"})
                         except Exception as e:
                             await websocket.send_json({"type": "error", "content": f"❌ Error al cambiar modelo: {e}"})
                    else:
                        current = adapter.llm_service.model_name
                        msg = f"**Modelo Actual:** `{current}`\n\nPara cambiar: `%models <nombre_modelo>` (ej: `gpt-4o`, `gemini/gemini-1.5-pro`)"
                        await websocket.send_json({"type": "chunk", "content": msg})
                        await websocket.send_json({"type": "done"})
                    continue

                elif cmd == "compress":
                    force = "force" in args
                    await websocket.send_json({"type": "info", "content": "🗜️ Comprimiendo historial..."})
                    summary = adapter.llm_service.summarize_conversation_history(force_truncate=force)
                    # Update state with summary logic (similar to MetaCommandProcessor)
                    from kogniterm.core.agents.bash_agent import SYSTEM_MESSAGE
                    from langchain_core.messages import AIMessage
                    
                    if not summary.startswith("Error"):
                        adapter.llm_service.conversation_history = [SYSTEM_MESSAGE, AIMessage(content=summary)]
                        adapter.agent_state.messages = adapter.llm_service.conversation_history
                        adapter.llm_service._save_history(adapter.llm_service.conversation_history)
                        await websocket.send_json({"type": "chunk", "content": f"**Historial Comprimido:**\n{summary}"})
                    else:
                         await websocket.send_json({"type": "error", "content": summary})
                    
                    await websocket.send_json({"type": "done"})
                    continue

                elif cmd == "init":
                     files = args[0].split(",") if args else None
                     
                     msg = "Inicializando contexto del espacio de trabajo"
                     if files:
                         msg += f" con: {', '.join(files)}"
                     else:
                         msg += " (completo)..."
                     
                     await websocket.send_json({"type": "info", "content": f"⏳ {msg}"})
                     
                     try:
                         # Run in executor to avoid blocking the event loop
                         loop = asyncio.get_event_loop()
                         await loop.run_in_executor(
                            executor, 
                            lambda: adapter.llm_service.initialize_workspace_context(files_to_include=files)
                         )
                         await websocket.send_json({"type": "info", "content": "✅ Contexto inicializado correctamente."})
                     except Exception as e:
                         await websocket.send_json({"type": "error", "content": f"Error: {e}"})
                     continue
                
                # If command not recognized/handled but started with % or /, treat as chat or warn?
                # For now, let it fall through to chat if it's not one of specific ones, 
                # OR handle as "unknown command" to avoid LLM hallucinating a response to a system command.
                
                # Let's return "Unknown command" for explicit safety if it started with %
                if user_message.startswith("%"):
                     await websocket.send_json({"type": "error", "content": f"Comando desconocido: {cmd}"})
                     continue

            # Fall through to normal chat processing for everything else

            if not user_message:
                continue

            # Process the message in a thread pool since it's a blocking generator
            loop = asyncio.get_event_loop()
            
            def run_invoke():
                # We need to add the user message to history first or pass it to invoke
                # The current terminal app adds it to history usually.
                # Actually LLMService.invoke takes 'history' but we need to manage it.
                
                # Simple implementation: just call the generator
                # We might want to yield chunks as they come
                responses = []
                for chunk in adapter.llm_service.invoke(history=adapter.agent_state.messages):
                    # In a more advanced implementation, we would send chunks directly here
                    # but this function runs in a thread, so we can't easily await websocket.send
                    responses.append(chunk)
                return responses

            # Improved approach: Send chunks via websocket from inside the thread?
            # Better: use a queue or just iterate in a thread and use loop.call_soon_threadsafe
            
            async def process_and_send():
                # This is a bit tricky with blocking generators. 
                # Let's try to iterate the generator in the threadpool and send chunks
                
                def iterate_gen():
                    for chunk in adapter.llm_service.invoke():
                        # We'll use this inside an async loop
                        yield chunk

                # For now, let's do a simple non-streaming return to verify things work
                # and then optimize for real streaming.
                
                # TO-DO: Implement real-time chunking via some mechanism
                pass

            # Temporary implementation: Run the whole thing and return
            # (We will improve this to be real streaming)
            
            # Let's actually try to do real streaming using a wrapper
            from kogniterm.core.history_manager import HumanMessage, AIMessage, ToolMessage
            
            # Add human message to history
            adapter.agent_state.messages.append(HumanMessage(content=user_message))
            
            # Run the generator in a separate thread
            def generate():
                step_limit = 10  # Evitar bucles infinitos
                current_step = 0
                
                while current_step < step_limit:
                    current_step += 1
                    
                    full_response = ""
                    in_reasoning = False
                    tool_calls_count = 0
                    final_tool_calls_detected = []
                    
                    # Variables para el mensaje final de este paso
                    last_ai_message = None

                    def detect_tools_in_text(content_text, current_count):
                        # Usar la lógica oficial del LLMService para detectar herramientas en texto
                        all_tools = adapter.llm_service._parse_tool_calls_from_text(content_text)
                        if len(all_tools) > current_count:
                            new_tools = all_tools[current_count:]
                            for tc in new_tools:
                                asyncio.run_coroutine_threadsafe(
                                    websocket.send_json({
                                        "type": "tool_call",
                                        "id": tc.get('id'),
                                        "name": tc.get('name'),
                                        "args": tc.get('args')
                                    }),
                                    loop
                                )
                            return len(all_tools), all_tools
                        return current_count, all_tools

                    # 1. GENERACIÓN (Llamada al LLM)
                    for chunk in adapter.llm_service.invoke(history=adapter.agent_state.messages):
                        # Si es un AIMessage completo (usualmente al final del yield de invoke)
                        if isinstance(chunk, AIMessage):
                            last_ai_message = chunk
                            # Si tiene tool_calls nativos
                            if chunk.tool_calls:
                                for tc in chunk.tool_calls:
                                    # Asegurar que no los hayamos enviado ya por detección de texto
                                    already_sent = False
                                    for sent_tc in final_tool_calls_detected:
                                        if sent_tc.get('name') == tc.get('name') and sent_tc.get('args') == tc.get('args'):
                                            already_sent = True
                                            break
                                    
                                    if not already_sent:
                                        asyncio.run_coroutine_threadsafe(
                                            websocket.send_json({
                                                "type": "tool_call",
                                                "id": tc.get('id'),
                                                "name": tc.get('name'),
                                                "args": tc.get('args')
                                            }),
                                            loop
                                        )
                            continue
                            
                        # Si es un chunk de texto (o string)
                        raw_content = str(chunk.content) if hasattr(chunk, 'content') else str(chunk)
                        
                        full_response += raw_content
                        
                        # Manejo de razonamiento
                        msg_type = "chunk"
                        
                        # 1. Razonamiento Nativo (prefijo por chunk)
                        if raw_content.startswith("__THINKING__:"):
                            msg_type = "reasoning"
                            raw_content = raw_content.replace("__THINKING__:", "", 1)
                            # NO activamos in_reasoning persistente porque cada chunk nativo trae su etiqueta
                        
                        # 2. Razonamiento Manual (persistente hasta cierto punto)
                        elif raw_content.strip().startswith("PENSAMIENTO:") or in_reasoning:
                            if raw_content.strip().startswith("PENSAMIENTO:"):
                                in_reasoning = True
                                raw_content = raw_content.replace("PENSAMIENTO:", "", 1)
                            
                            # Heurística simple: Si detectamos una herramienta, salimos.
                            # Si detectamos un patrón de salida claro, salimos.
                            # Por seguridad, si el usuario tiene este problema, haremos que el estado manual
                            # sea menos agresivo o confíe en tool_calls
                            msg_type = "reasoning"
                        
                        # Detección de herramientas en texto (siempre activa)
                        old_count = tool_calls_count
                        tool_calls_count, current_tools = detect_tools_in_text(full_response, tool_calls_count)
                        if tool_calls_count > old_count:
                            in_reasoning = False
                            msg_type = "chunk" # Si hay herramienta, asumimos que es acción, no solo pensamiento
                            final_tool_calls_detected = current_tools 

                        asyncio.run_coroutine_threadsafe(
                            websocket.send_json({"type": msg_type, "content": raw_content}),
                            loop
                        )
                    
                    # Al finalizar el streaming de este paso:
                    
                    # 1. Asegurar que el mensaje del asistente se guarde en el historial
                    # Si invoke no devolvió un AIMessage final (raro pero posible), lo creamos
                    if not last_ai_message:
                        last_ai_message = AIMessage(content=full_response, tool_calls=final_tool_calls_detected)
                    else:
                        # Fusionar los tool_calls detectados por texto con los del mensaje si faltan
                        if final_tool_calls_detected:
                            existing_calls = last_ai_message.tool_calls or []
                            # (Lógica simplificada de fusión: si no hay tools, usar las detectadas)
                            if not existing_calls:
                               last_ai_message.tool_calls = final_tool_calls_detected

                    adapter.agent_state.messages.append(last_ai_message)

                    # 2. EJECUCIÓN DE HERRAMIENTAS
                    if last_ai_message.tool_calls:
                        # Ejecutar todas las herramientas
                        for tc in last_ai_message.tool_calls:
                            tool_name = tc.get('name')
                            tool_args = tc.get('args') or {}
                            tool_id = tc.get('id')
                            
                            # Buscar la herramienta
                            tool = adapter.llm_service.tool_manager.get_tool(tool_name)
                            result_content = ""
                            
                            if tool:
                                try:
                                    # Ejecutar
                                    result_content = tool.invoke(tool_args)
                                except Exception as e:
                                    result_content = f"Error ejecutando herramienta {tool_name}: {str(e)}"
                            else:
                                result_content = f"Error: La herramienta '{tool_name}' no existe."
                            
                            # Crear y guardar ToolMessage
                            tool_msg = ToolMessage(content=str(result_content), tool_call_id=tool_id)
                            adapter.agent_state.messages.append(tool_msg)
                            
                            # Enviar resultado al frontend
                            asyncio.run_coroutine_threadsafe(
                                websocket.send_json({
                                    "type": "tool_result", 
                                    "content": str(result_content),
                                    "tool_call_id": tool_id
                                }),
                                loop
                            )
                        
                        # SI HUBO HERRAMIENTAS, CONTINUAR EL BUCLE (Siguiente paso del agente)
                        continue
                    
                    # Si no hubo herramientas, terminamos
                    break

                return full_response

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(executor, generate)
            
            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.send_json({"type": "error", "content": str(e)})
