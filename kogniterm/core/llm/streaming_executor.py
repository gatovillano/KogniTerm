import time
import json
import logging
import queue
import sys
from typing import Generator, Union, List, Dict, Any, Optional
from langchain_core.messages import AIMessage, BaseMessage
from litellm import completion

logger = logging.getLogger(__name__)

class StreamingExecutor:
    def __init__(self, provider_config, interrupt_queue: Optional[queue.Queue] = None):
        self.provider_config = provider_config
        self.interrupt_queue = interrupt_queue
        self.stop_generation_flag = False

    def execute_stream(self, completion_kwargs, parse_fn, id_gen_fn) -> Generator[Union[AIMessage, str], None, None]:
        """Ejecuta el stream de LiteLLM, maneja chunks, razonamiento y tool_calls."""
        self.stop_generation_flag = False
        full_response_content = ""
        full_reasoning_content = ""
        tool_calls = []
        
        try:
            # 1. Obtener el generador (con fallback automático si se configuró en ProviderManager)
            # El orquestador (LLMService) puede pasar el generador ya configurado
            if "response_generator" in completion_kwargs:
                response_generator = completion_kwargs.pop("response_generator")
            else:
                response_generator = completion(**completion_kwargs)
            
            start_time = time.time()

            last_chunk_time = time.time()
            chunk_timeout = 120
            overall_timeout = 900
            
            for chunk in response_generator:
                current_time = time.time()
                
                # Check timeouts
                if (current_time - last_chunk_time) > chunk_timeout:
                    logger.error("Conexión estancada.")
                    yield f"\n\n⚠️ Error: Conexión estancada.\n"
                    break
                
                if (current_time - start_time) > overall_timeout:
                    logger.error("Timeout total alcanzado.")
                    yield f"\n\n⚠️ Error: Tiempo de espera agotado.\n"
                    break
                
                last_chunk_time = current_time

                # Check interrupción
                if self.interrupt_queue and not self.interrupt_queue.empty():
                    while not self.interrupt_queue.empty():
                        self.interrupt_queue.get_nowait()
                    self.stop_generation_flag = True
                    break

                if self.stop_generation_flag: break

                choices = getattr(chunk, 'choices', None)
                if not choices or not isinstance(choices, list) or not choices[0]: continue
                
                delta = getattr(choices[0], 'delta', None)
                if not delta: continue

                # Capturar razonamiento
                reasoning_delta = getattr(delta, 'reasoning_content', None)
                if reasoning_delta is not None:
                    full_reasoning_content += str(reasoning_delta)
                    yield f"__THINKING__:{reasoning_delta}"

                # Capturar contenido
                if getattr(delta, 'content', None) is not None:
                    full_response_content += str(delta.content)
                    yield str(delta.content)
                
                # Capturar Tool Calls
                tool_calls_from_delta = getattr(delta, 'tool_calls', None)
                if tool_calls_from_delta is not None:
                    for tc in tool_calls_from_delta:
                        idx = getattr(tc, 'index', 0)
                        while idx >= len(tool_calls):
                            tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})
                        
                        if getattr(tc, 'id', None) is not None:
                            tool_calls[idx]["id"] = tc.id
                        elif not tool_calls[idx]["id"]:
                            tool_calls[idx]["id"] = id_gen_fn()
                        
                        if getattr(tc, 'function', None) is not None:
                            if getattr(tc.function, 'name', None) is not None and tc.function.name:
                                tool_calls[idx]["function"]["name"] = tc.function.name
                            if getattr(tc.function, 'arguments', None) is not None:
                                tool_calls[idx]["function"]["arguments"] += str(tc.function.arguments)

            if self.stop_generation_flag:
                yield AIMessage(content="Generación de respuesta interrumpida por el usuario. 🛑")
            else:
                # Consolidar tool_calls (nativos + parsed)
                final_tool_calls = self._consolidate_tool_calls(
                    tool_calls, 
                    full_response_content, 
                    full_reasoning_content, 
                    parse_fn
                )
                
                if final_tool_calls:
                    if not full_response_content.strip():
                        full_response_content = ""
                    yield AIMessage(
                        content=full_response_content,
                        tool_calls=final_tool_calls,
                        additional_kwargs={"reasoning_content": full_reasoning_content} if full_reasoning_content else {}
                    )
                else:
                    if not full_response_content.strip():
                        full_response_content = "Respuesta vacía del modelo."
                    yield AIMessage(
                        content=full_response_content,
                        additional_kwargs={"reasoning_content": full_reasoning_content} if full_reasoning_content else {}
                    )

        except Exception as e:
            logger.error(f"Error in execution: {e}")
            raise e

    def _consolidate_tool_calls(self, native_calls, content, reasoning, parse_fn) -> List[Dict[str, Any]]:
        final_tool_calls = []
        
        # 1. Herramientas nativas
        for tc in native_calls:
            try:
                args = json.loads(tc["function"]["arguments"]) if tc["function"]["arguments"] else {}
            except json.JSONDecodeError:
                args = {}
            final_tool_calls.append({
                "id": tc["id"],
                "name": tc["function"]["name"],
                "args": args
            })
            
        # 2. Herramientas parseadas del texto
        combined_text = "\n".join([content, reasoning])
        if combined_text.strip():
            text_tool_calls = parse_fn(combined_text)
            for tc_text in text_tool_calls:
                found = next((tc for tc in final_tool_calls if tc['name'] == tc_text['name']), None)
                if found:
                    if not found['args'] and tc_text.get('args'):
                        found['args'] = tc_text['args']
                else:
                    final_tool_calls.append(tc_text)
                    
        return final_tool_calls
