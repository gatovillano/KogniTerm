import logging
from litellm import completion
from .message_converter import from_litellm_message

logger = logging.getLogger(__name__)

class FallbackHandler:
    @staticmethod
    def handle_tool_error(error, completion_kwargs, model_name, id_gen_fn):
        """Maneja errores de soporte nativo de herramientas activando Bypass."""
        error_msg = str(error)
        is_tool_error = (
            ("20015" in error_msg and "Input should be 'function'" in error_msg) or 
            ("20015" in error_msg and "Field required" in error_msg and "openrouter" in model_name.lower()) or
            ("No endpoints found that support tool use" in error_msg)
        )

        if is_tool_error:
            logger.info(f"🔄 Activando MODO BYPASS para {model_name}...")
            
            # Preparar mensajes con herramientas inyectadas
            messages_with_tools = [m.copy() for m in completion_kwargs["messages"]]
            
            if "No endpoints found" in error_msg:
                tools_desc = "\n\n### HERRAMIENTAS DISPONIBLES (MODO BYPASS)\n"
                tools_desc += "ESTE MODELO NO SOPORTA TOOLS NATIVAS. FORMATO PARA LLAMAR:\n"
                tools_desc += "LLAMADA_A_HERRAMIENTA: nombre_herramienta {\"arg1\": \"valor1\"}\n\n"
                if completion_kwargs.get("tools"):
                    for t in completion_kwargs["tools"]:
                        func = t.get("function", t)
                        tools_desc += f"- **{func.get('name')}**: {func.get('description', '')}\n"
                
                if messages_with_tools and messages_with_tools[0]["role"] == "system":
                    messages_with_tools[0]["content"] += tools_desc
                else:
                    messages_with_tools.insert(0, {"role": "system", "content": tools_desc})

            alt_kwargs = {
                "model": completion_kwargs["model"],
                "messages": messages_with_tools,
                "stream": True,
                "api_key": completion_kwargs["api_key"],
                "temperature": completion_kwargs.get("temperature", 0.7),
                "max_tokens": 4096,
                "user": f"user_{id_gen_fn(12)}",
                "num_retries": 1, 
                "timeout": 90
            }
            
            # Aplicar reasoning_effort si está configurado
            if completion_kwargs.get("reasoning_effort"):
                alt_kwargs["reasoning_effort"] = completion_kwargs["reasoning_effort"]
            
            if "No endpoints found" in error_msg:
                alt_kwargs.pop("tools", None)
                alt_kwargs.pop("tool_choice", None)
            
            return completion(**alt_kwargs)
        
        raise error
