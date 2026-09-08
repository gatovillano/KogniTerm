import asyncio
import inspect
import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

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


class LLMBridge:
    """Puente delgado sobre LiteLLM para el fast path KAI-CLI-like."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or os.environ.get("LITELLM_MODEL") or _DEFAULT_FAST_PATH_MODEL
        self.provider_manager = get_provider_manager()
        self.adapter = get_default_adapter()

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
        elif provider.name == "kilocode":
            kwargs["custom_llm_provider"] = "openai"
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
    ) -> AsyncGenerator[Dict[str, Any], None]:
        tool_schemas = tools if tools is not None else self.adapter.get_schemas_for_litellm()
        resolved_model, provider_kwargs = self._resolve_model_provider(self.model)

        step_count = 0
        final_accumulated_content = ""

        while step_count < max_steps:
            step_count += 1
            call_kwargs = self._build_litellm_kwargs(tools=tool_schemas, model=resolved_model)
            call_kwargs["messages"] = messages
            call_kwargs.update(provider_kwargs)

            accumulated_content = ""
            tool_calls_dict: Dict[int, Dict[str, Any]] = {}

            try:
                response = await litellm.acompletion(**call_kwargs, timeout=120)
                async for chunk in response:
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

                    content = getattr(delta, "content", "") or ""
                    if content:
                        accumulated_content += content
                        final_accumulated_content += content
                        yield {"type": "content", "text": content}

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

            for tc in formatted_tool_calls:
                t_id = tc["id"]
                t_name = tc["function"]["name"]
                try:
                    t_args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    t_args = {}

                yield {"type": "tool_start", "name": t_name, "args": t_args}
                try:
                    result = await self.execute_tool_call(t_name, t_args)
                    yield {"type": "tool_result", "name": t_name, "result": result}
                    result_str = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                except Exception as exc:
                    result_str = f"Error ejecutando herramienta '{t_name}': {exc}"
                    yield {"type": "error", "message": result_str}

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": t_id,
                        "name": t_name,
                        "content": result_str,
                    }
                )

        yield {"type": "done", "content": final_accumulated_content}
