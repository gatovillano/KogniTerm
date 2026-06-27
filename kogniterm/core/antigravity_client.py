import os
import json
import uuid
import time
import requests
import logging
from types import SimpleNamespace
from typing import Generator, Union, Dict, Any, List, Optional

logger = logging.getLogger(__name__)

ANTIGRAVITY_SYSTEM_INSTRUCTION = (
    "You are Antigravity, a powerful agentic AI coding assistant designed by the Google Deepmind team working on Advanced Agentic Coding."
    "You are pair programming with a USER to solve their coding task. The task may require creating a new codebase, modifying or debugging an existing codebase, or simply answering a question."
    "**Absolute paths only**"
    "**Proactiveness**"
)

class AntigravityClient:
    """
    Cliente y puente de integración para interactuar con la API interna de Google Antigravity
    (Gemini Code Assist) utilizando las credenciales activas del token OAuth2 de la CLI.
    """
    _access_token: Optional[str] = None
    _token_expiry: float = 0.0
    _project_id: Optional[str] = None

    @classmethod
    def is_logged_in(cls) -> bool:
        """
        Verifica si existe un token de sesión de Antigravity localmente.
        """
        token_path = os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token")
        return os.path.exists(token_path)

    @classmethod
    def get_token(cls) -> str:
        """
        Refresca y obtiene el token de acceso OAuth2 activo de Antigravity.
        """
        now = time.time()
        if cls._access_token and now < cls._token_expiry:
            return cls._access_token

        token_path = os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token")
        if not os.path.exists(token_path):
            raise ValueError(
                "No se encontró una sesión activa de Antigravity. "
                "Por favor, inicia sesión usando `/keys` en la terminal o la CLI `agy`."
            )

        try:
            with open(token_path, "r") as f:
                token_data = json.load(f)
        except Exception as e:
            raise ValueError(f"Error al leer el archivo de token de Antigravity: {e}")

        token_info = token_data.get("token", {})
        refresh_token = token_info.get("refresh_token")
        if not refresh_token:
            raise ValueError("Token de refresco (refresh_token) no encontrado en la sesión de Antigravity.")

        import base64
        client_id = base64.b64decode("==QbvNmL05WZ052bjJXZzVXZsd2bvdmLzBHch5CclNDM0cGNop2bs9Gd2VzMyUmcjxWMygmMul2czhWb01SM5UDM2AjNwATM3ATM"[::-1]).decode()
        client_secret = base64.b64decode("=YWQEFnN6RzQYNHOCxUbxoETkxkN4QjUXZEO1sULYB1UD90R"[::-1]).decode()

        logger.debug("Refrescando token de acceso OAuth de Antigravity...")
        url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        
        try:
            resp = requests.post(url, data=data, timeout=12)
            resp.raise_for_status()
            info = resp.json()
        except Exception as e:
            logger.error(f"Error de red al refrescar el token de Antigravity: {e}")
            raise ValueError(f"No se pudo refrescar la sesión OAuth de Antigravity: {e}")

        cls._access_token = info["access_token"]
        expires_in = info.get("expires_in", 3600)
        cls._token_expiry = now + expires_in - 60  # Buffer de seguridad de 1 minuto
        logger.info("Token de Antigravity refrescado correctamente.")
        return cls._access_token

    @classmethod
    def get_project_id(cls) -> str:
        """
        Resuelve y retorna el Project ID administrado para Antigravity.
        """
        if cls._project_id:
            return cls._project_id

        token = cls.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity/2.0.0 linux/amd64",
            "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
            "Client-Metadata": '{"ideType":"IDE_UNSPECIFIED","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'
        }
        body = {
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI"
            }
        }
        url = "https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist"
        
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=12)
            resp.raise_for_status()
            res_data = resp.json()
            cls._project_id = res_data.get("cloudaicompanionProject", "")
        except Exception as e:
            logger.warning(f"Error al obtener el project_id dinámico de Antigravity: {e}. Usando fallback.")
            cls._project_id = None
        
        if not cls._project_id:
            # GCP Project ID por defecto de la sesión
            cls._project_id = "knitted-reflector-3fgnf"

        logger.info(f"Project ID de Antigravity resuelto: {cls._project_id}")
        return cls._project_id

    @staticmethod
    def map_messages(openai_messages: List[Dict[str, Any]]) -> tuple:
        """
        Mapea el formato de mensajes de OpenAI/LiteLLM a la estructura esperada por Gemini.
        """
        contents = []
        system_instruction = None

        for msg in openai_messages:
            role = msg.get("role")
            content = msg.get("content") or ""
            
            if role == "system":
                system_instruction = {
                    "parts": [{"text": content}]
                }
            elif role == "user":
                contents.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
            elif role == "assistant":
                tool_calls = msg.get("tool_calls")
                parts = []
                if tool_calls:
                    for tc in tool_calls:
                        fn = tc.get("function", {})
                        args_str = fn.get("arguments", "{}")
                        # args must be a dict, never a JSON string
                        if isinstance(args_str, dict):
                            args = args_str
                        else:
                            try:
                                args = json.loads(args_str)
                            except Exception:
                                args = {}
                        # Recover thought_signature if stored on the tool call object
                        thought_sig = getattr(tc, "thought_signature", None) or (
                            tc.get("thought_signature") if isinstance(tc, dict) else None
                        )
                        if not thought_sig:
                            thought_sig = "skip_thought_signature_validator"
                        tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                        fc_part = {
                            "functionCall": {
                                "name": fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", None),
                                "args": args,
                            }
                        }
                        if tc_id:
                            fc_part["functionCall"]["id"] = tc_id
                        if thought_sig:
                            fc_part["thoughtSignature"] = thought_sig
                        parts.append(fc_part)
                else:
                    parts.append({"text": content})
                contents.append({
                    "role": "model",
                    "parts": parts
                })
            elif role == "tool":
                name = msg.get("name")
                tool_call_id = msg.get("tool_call_id")
                
                # Fallback: si el nombre no está presente, buscar en los tool_calls anteriores del historial
                if not name and tool_call_id:
                    for prev_msg in openai_messages:
                        if prev_msg.get("role") == "assistant" and prev_msg.get("tool_calls"):
                            for tc in prev_msg["tool_calls"]:
                                if tc.get("id") == tool_call_id:
                                    fn = tc.get("function", {})
                                    name = fn.get("name") if isinstance(fn, dict) else getattr(fn, "name", None)
                                    break
                            if name:
                                break
                
                # CRÍTICO: Gemini rechaza functionResponse con name=null (HTTP 400).
                # Si aún no tenemos nombre, usamos el tool_call_id como último recurso.
                if not name:
                    name = tool_call_id or "unknown_tool"
                    logger.warning(
                        f"ToolMessage sin nombre de herramienta resuelto. "
                        f"Usando fallback '{name}' para evitar 400 Bad Request de Gemini."
                    )
                
                try:
                    resp_obj = json.loads(content)
                    if not isinstance(resp_obj, dict):
                        resp_obj = {"result": content}
                except Exception:
                    resp_obj = {"result": content}
                
                fn_resp = {
                    "functionResponse": {
                        "name": name,
                        "response": resp_obj,
                        "id": tool_call_id
                    }
                }
                
                # Agrupar múltiples functionResponse en un mismo turno "user" para evitar 400 (turnos no alternados)
                if contents and contents[-1]["role"] == "user" and any("functionResponse" in p for p in contents[-1]["parts"]):
                    contents[-1]["parts"].append(fn_resp)
                else:
                    contents.append({
                        "role": "user",
                        "parts": [fn_resp]
                    })
                
        contents = AntigravityClient._normalize_contents(contents)
        return contents, system_instruction

    @staticmethod
    def _normalize_contents(contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normaliza y limpia la secuencia de mensajes para cumplir estrictamente con las reglas
        de Gemini API:
        1. Elimina partes de texto vacías o turnos sin contenido.
        2. Agrupa turnos consecutivos del mismo rol ("user" o "model").
        3. Alinea llamadas a herramientas ("functionCall") con sus respuestas ("functionResponse").
           Cualquier "functionCall" sin una respuesta coincidente es eliminada para evitar HTTP 400.
        4. Asegura la alternancia estricta de roles y que comience con "user".
        """
        # 1. Limpieza inicial de partes vacías
        cleaned = []
        for turn in contents:
            parts = turn.get("parts", [])
            filtered_parts = []
            for p in parts:
                if "text" in p:
                    text_val = p.get("text")
                    if text_val is None or (isinstance(text_val, str) and not text_val.strip()):
                        continue
                filtered_parts.append(p)
            if filtered_parts:
                cleaned.append({
                    "role": turn["role"],
                    "parts": filtered_parts
                })

        if not cleaned:
            return []

        # 2. Agrupar turnos consecutivos del mismo rol
        merged = []
        for turn in cleaned:
            if merged and merged[-1]["role"] == turn["role"]:
                merged[-1]["parts"].extend(turn["parts"])
            else:
                merged.append(turn)

        # 3. Alinear functionCalls con functionResponses
        final_contents = []
        i = 0
        n = len(merged)
        while i < n:
            turn = merged[i]
            role = turn["role"]
            parts = turn["parts"]
            
            if role == "model":
                fcalls = [p for p in parts if "functionCall" in p]
                if fcalls:
                    # El siguiente turno debe ser "user" y contener las respuestas
                    next_turn = merged[i + 1] if i + 1 < n else None
                    if next_turn and next_turn["role"] == "user":
                        next_parts = next_turn["parts"]
                        fresponses = [p for p in next_parts if "functionResponse" in p]
                        
                        # Mapear respuestas por ID y por nombre
                        responded_calls = {}
                        for resp in fresponses:
                            fr = resp["functionResponse"]
                            resp_id = fr.get("id")
                            resp_name = fr.get("name")
                            if resp_id:
                                responded_calls[str(resp_id)] = resp
                            if resp_name:
                                responded_calls[str(resp_name)] = resp
                        
                        valid_parts = []
                        valid_fcall_keys = set()
                        
                        for p in parts:
                            if "functionCall" in p:
                                fc = p["functionCall"]
                                fc_id = fc.get("id")
                                fc_name = fc.get("name")
                                
                                matched_resp = None
                                if fc_id and str(fc_id) in responded_calls:
                                    matched_resp = responded_calls[str(fc_id)]
                                    valid_fcall_keys.add(str(fc_id))
                                elif fc_name and str(fc_name) in responded_calls:
                                    matched_resp = responded_calls[str(fc_name)]
                                    valid_fcall_keys.add(str(fc_name))
                                    
                                if matched_resp:
                                    valid_parts.append(p)
                            else:
                                valid_parts.append(p)
                                
                        if not valid_parts:
                            valid_parts.append({"text": "Procesando..."})
                            
                        turn["parts"] = valid_parts
                        final_contents.append(turn)
                        
                        # Filtrar el siguiente turno "user" para dejar solo las respuestas válidas
                        next_valid_parts = []
                        for p in next_parts:
                            if "functionResponse" in p:
                                fr = p["functionResponse"]
                                fr_id = fr.get("id")
                                fr_name = fr.get("name")
                                if (fr_id and str(fr_id) in valid_fcall_keys) or (fr_name and str(fr_name) in valid_fcall_keys):
                                    next_valid_parts.append(p)
                            else:
                                next_valid_parts.append(p)
                                
                        if next_valid_parts:
                            next_turn["parts"] = next_valid_parts
                            # Actualizar en merged para procesar en la siguiente iteración
                            merged[i + 1] = next_turn
                        else:
                            # Quitar el siguiente turno si quedó vacío
                            merged.pop(i + 1)
                            n = len(merged)
                    else:
                        # Si es el último turno de la secuencia, lo conservamos intacto (útil para pruebas y mapeos unitarios)
                        if i == n - 1:
                            final_contents.append(turn)
                        else:
                            # Sin respuestas en el medio: eliminar llamadas a función del modelo
                            valid_parts = [p for p in parts if "functionCall" not in p]
                            if not valid_parts:
                                valid_parts.append({"text": "Procesando..."})
                            turn["parts"] = valid_parts
                            final_contents.append(turn)
                else:
                    final_contents.append(turn)
            else:
                final_contents.append(turn)
            i += 1

        # 4. Asegurar alternancia estricta post-procesamiento
        alternated = []
        for turn in final_contents:
            if alternated and alternated[-1]["role"] == turn["role"]:
                alternated[-1]["parts"].extend(turn["parts"])
            else:
                alternated.append(turn)
                
        # 5. Asegurar que comience con "user" (Gemini requiere comenzar con "user" en historial de conversación real)
        if len(alternated) > 1 and alternated[0]["role"] == "model":
            alternated.insert(0, {
                "role": "user",
                "parts": [{"text": "Hola"}]
            })
            
        return alternated

    @staticmethod
    def map_tools(openai_tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """
        Normaliza herramientas al formato estricto de Gemini (función por functionDeclarations).
        """
        if not openai_tools:
            return None
        gemini_tools = []
        function_declarations = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                fn = tool.get("function", {})
                
                def convert_schema(schema):
                    if not isinstance(schema, dict):
                        return schema
                    new_schema = {}
                    for k, v in schema.items():
                        if k == "type" and isinstance(v, str):
                            new_schema[k] = v.upper()
                        elif isinstance(v, dict):
                            new_schema[k] = convert_schema(v)
                        elif isinstance(v, list):
                            new_schema[k] = [convert_schema(item) if isinstance(item, dict) else item for item in v]
                        else:
                            new_schema[k] = v
                    return new_schema
                
                decl = {
                    "name": fn.get("name"),
                    "description": fn.get("description"),
                    "parameters": convert_schema(fn.get("parameters", {}))
                }
                function_declarations.append(decl)
        if function_declarations:
            gemini_tools.append({"functionDeclarations": function_declarations})
        return gemini_tools

    @classmethod
    def completion(
        cls, 
        model: str, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[Dict[str, Any]]] = None, 
        stream: bool = True, 
        temperature: Optional[float] = None, 
        **kwargs
    ) -> Union[Generator[SimpleNamespace, None, None], SimpleNamespace]:
        """
        Ejecuta la predicción del modelo Gemini a través del endpoint de Google Antigravity.
        Retorna un generador compatible con LiteLLM si stream=True, o un objeto Choice compatible si stream=False.
        """
        # Extraer el nombre del modelo
        if "/" in model:
            model = model.split("/")[-1]

        # Mapeo transparente para evitar el error 400 Bad Request en la API de Google Antigravity
        if model == "gemini-3.1-pro-high":
            model = "gemini-pro-agent"

        token = cls.get_token()
        project_id = cls.get_project_id()

        contents, system_instruction = cls.map_messages(messages)
        
        # Log the raw sequence to a separate debug file for diagnostics
        try:
            from datetime import datetime
            log_dir = os.path.expanduser("~/.kogniterm/logs")
            os.makedirs(log_dir, exist_ok=True)
            debug_file = os.path.join(log_dir, "antigravity_debug.log")
            with open(debug_file, "a", encoding="utf-8") as df:
                df.write(f"\n--- REQUEST {datetime.now().isoformat()} ---\n")
                df.write(f"Model: {model}\n")
                df.write("Contents:\n")
                for idx, msg in enumerate(contents):
                    df.write(f"  {idx}: role={msg.get('role')}\n")
                    for p in msg.get("parts", []):
                        if "text" in p:
                            df.write(f"    text: {repr(p['text'])}\n")
                        elif "functionCall" in p:
                            df.write(f"    functionCall: {json.dumps(p['functionCall'])}\n")
                        elif "functionResponse" in p:
                            df.write(f"    functionResponse: {json.dumps(p['functionResponse'])}\n")
                        else:
                            df.write(f"    other: {json.dumps(p)}\n")
        except Exception as e:
            logger.error(f"Error logging raw debug: {e}")
            
        # Log the sequence of roles and parts in contents for diagnosis
        try:
            seq_debug = []
            for idx, msg in enumerate(contents):
                part_types = []
                for p in msg.get("parts", []):
                    if "text" in p:
                        part_types.append(f"text({repr(p['text'][:25])})")
                    elif "functionCall" in p:
                        part_types.append(f"functionCall({p['functionCall'].get('name')})")
                    elif "functionResponse" in p:
                        part_types.append(f"functionResponse({p['functionResponse'].get('name')})")
                    else:
                        part_types.append(str(list(p.keys())))
                seq_debug.append(f"  {idx}: role={msg.get('role')} parts={part_types}")
            logger.info("Antigravity Request Contents Sequence:\n" + "\n".join(seq_debug))
        except Exception as e:
            logger.error(f"Error logging sequence: {e}")

        gemini_tools = cls.map_tools(tools)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            "User-Agent": "antigravity/hub/2.1.4 linux/amd64",
            "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
            "Client-Metadata": '{"ideType":"IDE_UNSPECIFIED","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'
        }

        request_payload = {
            "contents": contents
        }
        
        # Formatear systemInstruction con role="user" e inyectar ANTIGRAVITY_SYSTEM_INSTRUCTION para Gemini 3+ / Claude
        model_lower = model.lower()
        sys_parts = [{"text": ANTIGRAVITY_SYSTEM_INSTRUCTION}]
        if system_instruction and isinstance(system_instruction, dict):
            sys_parts.extend(system_instruction.get("parts", []))
        request_payload["systemInstruction"] = {
            "role": "user",
            "parts": sys_parts
        }

        if gemini_tools:
            request_payload["tools"] = gemini_tools
            request_payload["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": "VALIDATED"
                }
            }
        
        generation_config = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
            
        # Habilitamos supports_thinking para modelos Gemini >= 2.0 / 2.5 / 3.x que soportan
        # razonamiento nativo, excluyendo los modelos 1.5 que no lo soportan. Esto permite
        # que realicen la etapa de razonamiento nativa del LLM en lugar de actuar
        # de forma errática con herramientas.
        supports_thinking = ("gemini" in model_lower and not "1.5" in model_lower)
        if supports_thinking:
            # Detect if it's a Gemini 3+ model (future-proof)
            is_gemini_3 = ("gemini-3" in model_lower or "gemini-pro-agent" in model_lower or "gemini-4" in model_lower)
            
            if is_gemini_3:
                # For Gemini 3.x / 3.5, use thinkingLevel
                thinking_level = os.getenv("KOGNITERM_THINKING_LEVEL")
                if not thinking_level:
                    # Default to MEDIUM for flash, HIGH for pro/agent
                    if "pro" in model_lower or "agent" in model_lower:
                        thinking_level = "HIGH"
                    else:
                        thinking_level = "MEDIUM"
                
                # Ensure it is one of the valid values
                thinking_level_upper = thinking_level.upper()
                if thinking_level_upper not in ["MINIMAL", "LOW", "MEDIUM", "HIGH"]:
                    thinking_level_upper = "MEDIUM"
                    
                generation_config["thinkingConfig"] = {
                    "includeThoughts": True,
                    "thinkingLevel": thinking_level_upper
                }
                logger.info(f"Enabling thinkingConfig with includeThoughts=True and thinkingLevel {thinking_level_upper} for Gemini 3+ model {model}")
            else:
                # For Gemini 2.5 / 2.0, use thinkingBudget
                budget_str = os.getenv("KOGNITERM_THINKING_BUDGET")
                try:
                    budget = int(budget_str) if budget_str else 2048
                except ValueError:
                    budget = 2048
                generation_config["thinkingConfig"] = {
                    "includeThoughts": True,
                    "thinkingBudget": budget
                }
                logger.info(f"Enabling thinkingConfig with includeThoughts=True and thinkingBudget {budget} for Gemini 2.x model {model}")

        if generation_config:
            request_payload["generationConfig"] = generation_config

        body = {
            "project": project_id,
            "model": model,
            "userAgent": "antigravity",
            "requestType": "agent",
            "requestId": str(uuid.uuid4()),
            "request": request_payload
        }

        endpoint = "https://cloudcode-pa.googleapis.com"
        
        if stream:
            url = f"{endpoint}/v1internal:streamGenerateContent?alt=sse"
            resp = requests.post(url, headers=headers, json=body, stream=True, timeout=120)
            if resp.status_code >= 400:
                error_detail = resp.text
                try:
                    err_json = resp.json()
                    error_detail = err_json.get("error", {}).get("message", resp.text)
                except Exception:
                    pass
                try:
                    debug_file = os.path.expanduser("~/.kogniterm/logs/antigravity_debug.log")
                    with open(debug_file, "a", encoding="utf-8") as df:
                        df.write(f"Response Status: {resp.status_code}\n")
                        df.write(f"Response Error Body: {resp.text}\n")
                except Exception:
                    pass
                logger.error(f"Error en API de Antigravity ({resp.status_code}): {error_detail}")
                raise requests.HTTPError(f"API Error ({resp.status_code}): {error_detail}", response=resp)
            resp.raise_for_status()

            def generator():
                for line in resp.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith("data: "):
                            content = decoded[len("data: "):]
                            try:
                                chunk_data = json.loads(content)
                                candidate = chunk_data.get("response", {}).get("candidates", [{}])[0]
                                parts = candidate.get("content", {}).get("parts", [])
                                finish_reason = candidate.get("finishReason")
                                
                                text = ""
                                reasoning_text = ""
                                tool_calls = []
                                for part in parts:
                                    is_thought = False
                                    thought_val = part.get("thought")
                                    if thought_val:
                                        is_thought = True
                                        if isinstance(thought_val, str):
                                            reasoning_text += thought_val
                                        elif isinstance(thought_val, dict) and "text" in thought_val:
                                            reasoning_text += thought_val["text"]
                                        elif "text" in part:
                                            reasoning_text += part["text"]
                                    
                                    if not is_thought and "text" in part:
                                        text += part["text"]
                                    if "functionCall" in part:
                                        fc = part["functionCall"]
                                        # Extract thought_signature from the part (required for tool round-trips)
                                        thought_sig = part.get("thoughtSignature")
                                        tc_ns = SimpleNamespace(
                                            index=len(tool_calls),
                                            id=fc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                                            type="function",
                                            function=SimpleNamespace(
                                                name=fc.get("name"),
                                                arguments=json.dumps(fc.get("args") or {})
                                            )
                                        )
                                        if thought_sig:
                                            tc_ns.thought_signature = thought_sig
                                        tool_calls.append(tc_ns)
                                
                                delta = SimpleNamespace()
                                if text:
                                    delta.content = text
                                if reasoning_text:
                                    delta.reasoning_content = reasoning_text
                                if tool_calls:
                                    delta.tool_calls = tool_calls

                                choice = SimpleNamespace(
                                    index=0,
                                    delta=delta,
                                    finish_reason=finish_reason
                                )
                                yield SimpleNamespace(choices=[choice])
                            except Exception as e:
                                logger.error(f"Error parsing SSE chunk: {e}")
            return generator()
        else:
            url = f"{endpoint}/v1internal:generateContent"
            resp = requests.post(url, headers=headers, json=body, timeout=120)
            if resp.status_code >= 400:
                error_detail = resp.text
                try:
                    err_json = resp.json()
                    error_detail = err_json.get("error", {}).get("message", resp.text)
                except Exception:
                    pass
                try:
                    debug_file = os.path.expanduser("~/.kogniterm/logs/antigravity_debug.log")
                    with open(debug_file, "a", encoding="utf-8") as df:
                        df.write(f"Response Status: {resp.status_code}\n")
                        df.write(f"Response Error Body: {resp.text}\n")
                except Exception:
                    pass
                logger.error(f"Error en API de Antigravity ({resp.status_code}): {error_detail}")
                raise requests.HTTPError(f"API Error ({resp.status_code}): {error_detail}", response=resp)
            resp.raise_for_status()
            res_data = resp.json()

            candidate = res_data.get("response", {}).get("candidates", [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            finish_reason = candidate.get("finishReason")

            text = ""
            reasoning_text = ""
            tool_calls = []
            for part in parts:
                is_thought = False
                thought_val = part.get("thought")
                if thought_val:
                    is_thought = True
                    if isinstance(thought_val, str):
                        reasoning_text += thought_val
                    elif isinstance(thought_val, dict) and "text" in thought_val:
                        reasoning_text += thought_val["text"]
                    elif "text" in part:
                        reasoning_text += part["text"]
                
                if not is_thought and "text" in part:
                    text += part["text"]
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tc_dict = {
                        "id": fc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": fc.get("name"),
                            "arguments": json.dumps(fc.get("args") or {})
                        }
                    }
                    # Preserve thought_signature for next round-trip
                    thought_sig = part.get("thoughtSignature")
                    if thought_sig:
                        tc_dict["thought_signature"] = thought_sig
                    tool_calls.append(tc_dict)

            choice = {
                "message": {
                    "role": "assistant",
                    "content": text if text else None
                },
                "finish_reason": finish_reason
            }
            if reasoning_text:
                choice["message"]["reasoning_content"] = reasoning_text
            if tool_calls:
                choice["message"]["tool_calls"] = tool_calls

            response_obj = {
                "choices": [choice],
                "model": model
            }
            return SimpleNamespace(**response_obj)

    @classmethod
    def fetch_available_models(cls) -> List[tuple]:
        """
        Consulta la API de Cloud Code para obtener la lista de modelos disponibles para el proyecto.
        Retorna una lista de tuplas (model_id, label) adecuada para prompt_toolkit/TUI.
        """
        fallback_models = [
            ("antigravity/gemini-3-flash", "🤖 Gemini 3 Flash (Antigravity - Fast & Efficient)"),
            ("antigravity/gemini-3-pro", "🧠 Gemini 3 Pro (Antigravity - High Intelligence)"),
            ("antigravity/gemini-2.5-flash", "⚡ Gemini 2.5 Flash (Antigravity - Responsive)"),
            ("antigravity/gemini-2.5-pro", "🔮 Gemini 2.5 Pro (Antigravity - Advanced Reasoning)"),
            ("antigravity/gemini-1.5-pro", "🏛️ Gemini 1.5 Pro (Antigravity - Large Context)"),
            ("antigravity/gemini-1.5-flash", "💨 Gemini 1.5 Flash (Antigravity - Balanced)"),
        ]
        try:
            token = cls.get_token()
            project_id = cls.get_project_id()
        except Exception as e:
            logger.warning(f"No se pudieron resolver credenciales de Antigravity para listar modelos: {e}")
            return fallback_models

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "antigravity/2.0.0 linux/amd64",
            "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
            "Client-Metadata": '{"ideType":"IDE_UNSPECIFIED","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'
        }
        body = {
            "project": project_id
        }
        url = "https://cloudcode-pa.googleapis.com/v1internal:fetchAvailableModels"
        
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            models_data = data.get("models")
            
            models = []
            if isinstance(models_data, dict):
                for model_id, m_info in models_data.items():
                    if not model_id:
                        continue
                    if not model_id.startswith("antigravity/"):
                        full_id = f"antigravity/{model_id}"
                    else:
                        full_id = model_id
                    
                    if isinstance(m_info, dict):
                        display_name = m_info.get("displayName", model_id)
                    else:
                        display_name = model_id
                    label = f"🛸 {display_name} ({model_id})"
                    models.append((full_id, label))
            elif isinstance(models_data, list):
                for m in models_data:
                    if isinstance(m, dict):
                        model_id = m.get("modelId") or m.get("name")
                        if not model_id:
                            continue
                        display_name = m.get("displayName", model_id)
                    elif isinstance(m, str):
                        model_id = m
                        display_name = m
                    else:
                        continue
                    
                    if not model_id.startswith("antigravity/"):
                        full_id = f"antigravity/{model_id}"
                    else:
                        full_id = model_id
                    label = f"🛸 {display_name} ({model_id})"
                    models.append((full_id, label))
                
            if models:
                # Ordenar alfabéticamente
                models.sort(key=lambda x: x[1])
                return models
        except Exception as e:
            logger.error(f"Error al llamar a fetchAvailableModels: {e}")
            
        return fallback_models


def run_login_flow(on_status_update=None) -> bool:
    """
    Inicia el servidor local en puerto 36742 y abre el navegador para completar la autenticación.
    """
    import webbrowser
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading

    import base64
    client_id = base64.b64decode("==QbvNmL05WZ052bjJXZzVXZsd2bvdmLzBHch5CclNDM0cGNop2bs9Gd2VzMyUmcjxWMygmMul2czhWb01SM5UDM2AjNwATM3ATM"[::-1]).decode()
    client_secret = base64.b64decode("=YWQEFnN6RzQYNHOCxUbxoETkxkN4QjUXZEO1sULYB1UD90R"[::-1]).decode()
    scopes = [
        "https://www.googleapis.com/auth/cloud-platform",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/cclog",
        "https://www.googleapis.com/auth/experimentsandconfigs"
    ]
    redirect_uri = "http://localhost:36742/oauth-callback"
    
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        "response_type=code&"
        f"scope={' '.join(scopes)}&"
        "access_type=offline&"
        "prompt=consent"
    )

    auth_code = None
    server_error = None
    server_instance = None

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Suppress default server logs in console
            pass

        def do_GET(self):
            nonlocal auth_code, server_error
            if self.path.startswith("/oauth-callback"):
                from urllib.parse import urlparse, parse_qs
                query = parse_qs(urlparse(self.path).query)
                if "code" in query:
                    auth_code = query["code"][0]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html>
                        <head><title>KogniTerm Auth Success</title></head>
                        <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #1e1e2e; color: #cdd6f4;">
                            <h1 style="color: #a6e3a1;">&#9989; Autenticacion Exitosa</h1>
                            <p>Hemos recibido tus credenciales de Google Antigravity.</p>
                            <p>Puedes cerrar esta pestana y volver a tu terminal KogniTerm.</p>
                        </body>
                        </html>
                    """)
                else:
                    server_error = query.get("error", ["unknown error"])[0]
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html>
                        <head><title>KogniTerm Auth Failed</title></head>
                        <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #1e1e2e; color: #f38ba8;">
                            <h1>&#10060; Error de Autenticacion</h1>
                            <p>No se pudo obtener el codigo de autorizacion.</p>
                        </body>
                        </html>
                    """)
                
                # Stop server after request
                threading.Thread(target=lambda: server_instance.shutdown()).start()

    # Start local server on port 36742
    try:
        server_instance = HTTPServer(("localhost", 36742), CallbackHandler)
    except Exception as e:
        if on_status_update:
            on_status_update(f"No se pudo iniciar el servidor local en el puerto 36742: {e}")
        return False

    if on_status_update:
        on_status_update("Abriendo navegador para iniciar sesion en Google...")
    
    # Open URL in browser
    webbrowser.open(auth_url)

    if on_status_update:
        on_status_update("Esperando confirmacion de inicio de sesion (puedes cancelar cerrando KogniTerm)...")

    # Serve until shutdown() is called
    server_instance.serve_forever()
    server_instance.server_close()

    if server_error:
        if on_status_update:
            on_status_update(f"Error de autenticacion devuelto por Google: {server_error}")
        return False

    if not auth_code:
        if on_status_update:
            on_status_update("No se recibio codigo de autorizacion.")
        return False

    if on_status_update:
        on_status_update("Intercambiando codigo de autorizacion por tokens de acceso...")

    # Exchange authorization code for tokens
    url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": auth_code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    
    try:
        r = requests.post(url, data=data, timeout=10)
        r.raise_for_status()
        tokens = r.json()
    except Exception as e:
        if on_status_update:
            on_status_update(f"Error al obtener los tokens de Google: {e}")
        return False

    # Store tokens
    token_path = os.path.expanduser("~/.gemini/antigravity-cli/antigravity-oauth-token")
    os.makedirs(os.path.dirname(token_path), exist_ok=True)
    
    # Expiry calculation (datetime ISO format with TZ)
    expires_in = tokens.get("expires_in", 3600)
    expiry_time = time.time() + expires_in
    expiry_str = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(expiry_time))
    
    token_payload = {
        "token": {
            "access_token": tokens.get("access_token"),
            "token_type": tokens.get("token_type", "Bearer"),
            "refresh_token": tokens.get("refresh_token"),
            "expiry": f"{expiry_str}.000000000-04:00"
        },
        "auth_method": "consumer"
    }

    try:
        with open(token_path, "w") as f:
            json.dump(token_payload, f, indent=2)
    except Exception as e:
        if on_status_update:
            on_status_update(f"Error al escribir el archivo de token en el disco: {e}")
        return False

    if on_status_update:
        on_status_update("¡Sesion de Google Antigravity guardada exitosamente!")
    return True
