import asyncio
import inspect
import json
import logging
import os
import re
import threading
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple

import litellm
from litellm.exceptions import (
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    ServiceUnavailableError,
)

from kogniterm.core.ai_cli_bridge.tool_registry_adapter import get_default_adapter
from kogniterm.core.multi_provider_manager import get_provider_manager

logger = logging.getLogger(__name__)

litellm.suppress_debug_info = True
litellm.drop_params = True

_DEFAULT_FAST_PATH_MODEL = "gemini/gemini-1.5-flash"


def _parse_text_tool_calls(text: str) -> Tuple[List[Dict[str, Any]], str]:
    """Detecta y extrae llamadas a herramientas en texto/XML/JSON cuando el modelo no usa tool_calls nativos."""
    if not text:
        return [], text

    tool_calls: List[Dict[str, Any]] = []
    clean_text = text

    # Formato 1: XML <invoke name="...">...</invoke>
    invoke_pattern = re.compile(
        r"<invoke\s+name=[\"'](?P<name>[^\"']+)[\"']>(?P<body>.*?)</invoke>",
        re.DOTALL,
    )
    for match in invoke_pattern.finditer(text):
        name = match.group("name").strip()
        body = match.group("body")
        args: Dict[str, Any] = {}

        param_pattern = re.compile(
            r"<parameter\s+name=[\"'](?P<pname>[^\"']+)[\"']>(?P<pval>.*?)</parameter>",
            re.DOTALL,
        )
        for pmatch in param_pattern.finditer(body):
            pname = pmatch.group("pname").strip()
            pval = pmatch.group("pval").strip()
            try:
                args[pname] = json.loads(pval)
            except Exception:
                args[pname] = pval

        tool_calls.append({"name": name, "arguments": args})

    if tool_calls:
        clean_text = invoke_pattern.sub("", clean_text)
        clean_text = re.sub(r"<\/?function_calls>", "", clean_text)

    # Formato 2: <tool_call>{"name": "...", "arguments": {...}}</tool_call>
    tool_call_tag_pattern = re.compile(r"<tool_call>(?P<body>.*?)</tool_call>", re.DOTALL)
    for match in tool_call_tag_pattern.finditer(clean_text):
        body = match.group("body").strip()
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict) and ("name" in parsed or "tool" in parsed):
                t_name = parsed.get("name") or parsed.get("tool")
                t_args = parsed.get("arguments") or parsed.get("args") or {}
                tool_calls.append({"name": t_name, "arguments": t_args})
        except Exception:
            pass

    if tool_call_tag_pattern.search(clean_text):
        clean_text = tool_call_tag_pattern.sub("", clean_text)

    return tool_calls, clean_text.strip()


_CONTINUATION_PATTERNS = [
    re.compile(r"\b(ahora|a continuación|seguidamente|paso siguiente|próximo paso)\s+(voy a|vamos a|procedo a|procederé a|ejecutaré|crearé|modificaré|revisaré|leeré|instalaré|probaré)", re.IGNORECASE),
    re.compile(r"\b(procedo a|procederé a)\s+(ejecutar|crear|modificar|revisar|leer|instalar|verificar|analizar|probar|hacer)", re.IGNORECASE),
    re.compile(r"\b(voy a|vamos a)\s+(ejecutar|crear|modificar|revisar|leer|instalar|verificar|analizar|probar|hacer)", re.IGNORECASE),
    re.compile(r"\b(paso \d+|step \d+)\b", re.IGNORECASE),
    re.compile(r"\b(let me (now|proceed)|i will now|next,?\s*i will|i am going to|proceeding to)\b", re.IGNORECASE),
]


def _detect_continuation_intent(text: str) -> bool:
    """Detecta si el texto del asistente promete una acción o siguiente paso sin haber adjuntado herramientas."""
    if not text:
        return False
    completion_markers = [
        "tarea completada", "tarea finalizada", "he completado", "hemos completado",
        "concluido con éxito", "finalizado con éxito", "todo listo", "proceso completado",
        "task completed", "successfully finished", "all done"
    ]
    text_lower = text.lower()
    if any(marker in text_lower for marker in completion_markers):
        return False

    return any(p.search(text) for p in _CONTINUATION_PATTERNS)


class LLMBridge:
    """Puente delgado sobre LiteLLM para el fast path KAI-CLI-like."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or os.environ.get("LITELLM_MODEL") or _DEFAULT_FAST_PATH_MODEL
        self.provider_manager = get_provider_manager()
        self.adapter = get_default_adapter()

    def set_model(self, model: str) -> None:
        """Actualiza el modelo activo del puente."""
        self.model = model

    def _resolve_model_provider(self, model_name: str):
        provider = self.provider_manager._determine_ideal_provider(model_name)
        if provider is None:
            return model_name, {}

        full_model = self.provider_manager._resolve_model_for_provider(provider, model_name)
        api_key = provider.get_api_key()
        api_base = provider.get_api_base()

        kwargs: Dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base

        if provider.name == "ollama":
            kwargs["custom_llm_provider"] = "ollama"
        elif provider.name == "ollama_cloud":
            kwargs["custom_llm_provider"] = "openai"
        elif provider.name in ("kilocode", "inception"):
            kwargs["custom_llm_provider"] = "openai"
        elif provider.name == "antigravity":
            kwargs["custom_llm_provider"] = "antigravity"
        elif provider.model_prefix == "gemini" or provider.name == "google":
            kwargs["custom_llm_provider"] = "gemini"
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key

        if provider.name == "openrouter":
            kwargs["headers"] = {
                "HTTP-Referer": "https://github.com/gatovillano/KogniTerm",
                "X-Title": "KogniTerm",
            }

        return full_model, kwargs


    def _build_litellm_kwargs(self, tools: Optional[List[Dict[str, Any]]] = None, model: Optional[str] = None) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "model": model or self.model,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return kwargs

    async def execute_tool_call(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "task_complete":
            return {"status": "completed", "message": args.get("message", "") or "Tarea completada."}
        if tool_name == "call_agent":
            return "call_agent no está soportado por el fast path en Fase 1."

        return await self.adapter.execute(tool_name, args)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_steps: int = 25,
        interrupt_queue: Optional[Any] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        model: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        def _is_interrupted() -> bool:
            if stop_check and stop_check():
                return True
            if interrupt_queue and not getattr(interrupt_queue, "empty", lambda: True)():
                return True
            return False

        target_model = model or self.model
        tool_schemas = tools if tools is not None else self.adapter.get_schemas_for_litellm()
        resolved_model, provider_kwargs = self._resolve_model_provider(target_model)

        step_count = 0
        nudge_count = 0
        max_nudges = 2
        final_accumulated_content = ""

        while step_count < max_steps:
            if _is_interrupted():
                yield {"type": "interrupted", "message": "Generación interrumpida por el usuario."}
                return

            step_count += 1
            call_kwargs = self._build_litellm_kwargs(tools=tool_schemas, model=resolved_model)
            call_kwargs["messages"] = messages
            call_kwargs.update(provider_kwargs)

            accumulated_content = ""
            tool_calls_dict: Dict[int, Dict[str, Any]] = {}
            in_think_tag = False
            in_func_tag = False

            try:
                if provider_kwargs.get("custom_llm_provider") == "antigravity":
                    from kogniterm.core.antigravity_client import AntigravityClient
                    def _get_ag_stream():
                        return AntigravityClient.completion(
                            model=resolved_model,
                            messages=messages,
                            tools=tool_schemas,
                            stream=True,
                        )
                    sync_gen = await asyncio.to_thread(_get_ag_stream)

                    loop = asyncio.get_running_loop()
                    q = asyncio.Queue()
                    def _worker():
                        try:
                            for item in sync_gen:
                                if _is_interrupted():
                                    break
                                loop.call_soon_threadsafe(q.put_nowait, ("item", item))
                            loop.call_soon_threadsafe(q.put_nowait, ("done", None))
                        except Exception as exc:
                            loop.call_soon_threadsafe(q.put_nowait, ("error", exc))

                    t = threading.Thread(target=_worker, daemon=True)
                    t.start()

                    async def _ag_stream_wrapper():
                        while True:
                            status, val = await q.get()
                            if status == "item":
                                yield val
                            elif status == "error":
                                raise val
                            elif status == "done":
                                break

                    response = _ag_stream_wrapper()
                else:
                    response = await litellm.acompletion(**call_kwargs, timeout=120)
                async for chunk in response:
                    if _is_interrupted():
                        yield {"type": "interrupted", "message": "Generación interrumpida por el usuario."}
                        return

                    choices = getattr(chunk, "choices", [])
                    if not choices:
                        continue
                    delta = choices[0].delta

                    reasoning_text = (
                        getattr(delta, "reasoning_content", None)
                        or getattr(delta, "thinking", None)
                        or getattr(delta, "reasoning", None)
                        or getattr(delta, "thinking_content", None)
                    )
                    if reasoning_text:
                        yield {"type": "reasoning", "text": reasoning_text}

                    raw_content = getattr(delta, "content", "") or ""
                    if raw_content:
                        # Normalizar etiquetas de pensamiento (<thought> -> <think>)
                        curr_text = raw_content.replace("<thought>", "<think>").replace("</thought>", "</think>")

                        # Suprimir streaming de bloques de herramientas en texto (<function_calls>, <invoke>, <tool_call>)
                        if any(tag in curr_text for tag in ("<function_calls>", "<invoke", "<tool_call>")):
                            in_func_tag = True

                        if in_func_tag:
                            accumulated_content += curr_text
                            if any(tag in curr_text for tag in ("</function_calls>", "</invoke>", "</tool_call>")):
                                in_func_tag = False
                            continue

                        # Filtrado en streaming de bloques <think>...</think>
                        if "<think>" in curr_text:
                            parts = curr_text.split("<think>", 1)
                            if parts[0]:
                                accumulated_content += parts[0]
                                final_accumulated_content += parts[0]
                                yield {"type": "content", "text": parts[0]}
                            in_think_tag = True
                            curr_text = parts[1]

                        if in_think_tag:
                            if "</think>" in curr_text:
                                think_parts = curr_text.split("</think>", 1)
                                if think_parts[0]:
                                    yield {"type": "reasoning", "text": think_parts[0]}
                                in_think_tag = False
                                remainder = think_parts[1]
                                if remainder:
                                    accumulated_content += remainder
                                    final_accumulated_content += remainder
                                    yield {"type": "content", "text": remainder}
                            else:
                                yield {"type": "reasoning", "text": curr_text}
                        else:
                            if "</think>" in curr_text:
                                remainder = curr_text.split("</think>", 1)[1]
                                if remainder:
                                    accumulated_content += remainder
                                    final_accumulated_content += remainder
                                    yield {"type": "content", "text": remainder}
                            else:
                                accumulated_content += curr_text
                                final_accumulated_content += curr_text
                                yield {"type": "content", "text": curr_text}

                    delta_tool_calls = getattr(delta, "tool_calls", None)
                    if delta_tool_calls:
                        for tc in delta_tool_calls:
                            idx = getattr(tc, "index", 0)
                            if idx not in tool_calls_dict:
                                tool_calls_dict[idx] = {
                                    "id": getattr(tc, "id", "") or f"call_{idx}",
                                    "name": "",
                                    "arguments": "",
                                }
                            tc_id = getattr(tc, "id", None)
                            if tc_id:
                                tool_calls_dict[idx]["id"] = tc_id

                            fn = getattr(tc, "function", None)
                            if fn:
                                fn_name = getattr(fn, "name", None)
                                if fn_name:
                                    cur_name = tool_calls_dict[idx]["name"]
                                    if not cur_name:
                                        tool_calls_dict[idx]["name"] = fn_name
                                    elif cur_name == fn_name or cur_name.endswith(fn_name):
                                        pass
                                    elif fn_name.startswith(cur_name):
                                        tool_calls_dict[idx]["name"] = fn_name
                                    else:
                                        tool_calls_dict[idx]["name"] += fn_name

                                fn_args = getattr(fn, "arguments", None)
                                if fn_args:
                                    tool_calls_dict[idx]["arguments"] += fn_args
            except AuthenticationError as exc:
                yield {"type": "error", "message": f"Error de autenticación: {exc}"}
                return
            except BadRequestError as exc:
                yield {"type": "error", "message": f"Petición inválida al modelo (Bad Request): {exc}"}
                return
            except (RateLimitError, ServiceUnavailableError, APIConnectionError) as exc:
                yield {"type": "error", "message": f"Error de comunicación con el proveedor ({type(exc).__name__}): {exc}"}
                return
            except Exception as exc:
                yield {"type": "error", "message": f"Error inesperado en LiteLLM: {exc}"}
                return

            if not tool_calls_dict:
                # Fallback: verificar si el LLM devolvió tool calls en texto o XML
                text_calls, clean_text = _parse_text_tool_calls(accumulated_content)
                if text_calls:
                    for i, tc in enumerate(text_calls):
                        tool_calls_dict[i] = {
                            "id": f"call_text_{step_count}_{i}",
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"], ensure_ascii=False) if isinstance(tc["arguments"], dict) else str(tc["arguments"]),
                        }
                    accumulated_content = clean_text
                elif nudge_count < max_nudges and _detect_continuation_intent(accumulated_content):
                    nudge_count += 1
                    logger.info(
                        f"LLMBridge: Detectada intención de continuación sin herramientas en paso {step_count} "
                        f"('{accumulated_content[:80]}...'). Enviando auto-nudge ({nudge_count}/{max_nudges})."
                    )
                    messages.append({"role": "assistant", "content": accumulated_content})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[SISTEMA ANTI-DETENCIÓN PREMATURA]: Has indicado que vas a continuar o ejecutar una acción, "
                            "pero NO has emitido ninguna llamada a herramienta (`tool_call`) en este turno. "
                            "El flujo de KogniTerm se detendrá si no llamas a una herramienta. "
                            "DEBES invocar INMEDIATAMENTE en este turno la herramienta correspondiente (`execute_command`, "
                            "`advanced_file_editor`, etc.) para realizar la acción. "
                            "Si la tarea ya está 100% terminada y verificada, presenta la respuesta final al usuario sin prometer acciones futuras."
                        ),
                    })
                    continue
                else:
                    messages.append({"role": "assistant", "content": accumulated_content})
                    yield {"type": "done", "content": final_accumulated_content}
                    return

            formatted_tool_calls = []
            for idx in sorted(tool_calls_dict.keys()):
                tc_data = tool_calls_dict[idx]
                formatted_tool_calls.append(
                    {
                        "id": tc_data["id"],
                        "type": "function",
                        "function": {
                            "name": tc_data["name"],
                            "arguments": tc_data["arguments"],
                        },
                    }
                )

            messages.append({"role": "assistant", "content": accumulated_content or None, "tool_calls": formatted_tool_calls})
            yield {
                "type": "tool_calls_start",
                "content": accumulated_content or "",
                "tool_calls": formatted_tool_calls,
            }

            for tc in formatted_tool_calls:
                if _is_interrupted():
                    yield {"type": "interrupted", "message": "Generación interrumpida por el usuario."}
                    return

                t_id = tc["id"]
                t_name = tc["function"]["name"]
                try:
                    t_args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    t_args = {}

                yield {"type": "tool_start", "name": t_name, "args": t_args, "id": t_id}
                try:
                    result = await self.execute_tool_call(t_name, t_args)
                    yield {"type": "tool_result", "name": t_name, "result": result, "id": t_id}
                    result_str = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                except Exception as exc:
                    result_str = f"Error ejecutando herramienta '{t_name}': {exc}"
                    yield {"type": "error", "message": result_str, "id": t_id}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": t_id,
                        "name": t_name,
                        "content": result_str,
                    }
                )

        yield {"type": "done", "content": final_accumulated_content}
