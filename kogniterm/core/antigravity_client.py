import os
import json
import uuid
import time
import requests
import logging
from types import SimpleNamespace
from typing import Generator, Union, Dict, Any, List, Optional

logger = logging.getLogger(__name__)

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
        client_id = base64.b64decode("MTA3MTAwNjA2MDU5MS10bWhzc2luMmgyMWxjcmUyMzV2dG9sb2poNGc0MDNlcC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbQ==").decode()
        client_secret = base64.b64decode("R09DU1BYLUs1OEZXUjQ4NkxkTEoxbUxCOHNYQzR6cURBZg==").decode()

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
                        try:
                            args = json.loads(args_str)
                        except Exception:
                            args = {}
                        parts.append({
                            "functionCall": {
                                "name": fn.get("name"),
                                "args": args,
                                "id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                            },
                            "thoughtSignature": "skip_thought_signature_validator"
                        })
                else:
                    parts.append({"text": content})
                contents.append({
                    "role": "model",
                    "parts": parts
                })
            elif role == "tool":
                name = msg.get("name")
                try:
                    resp_obj = json.loads(content)
                    if not isinstance(resp_obj, dict):
                        resp_obj = {"result": content}
                except Exception:
                    resp_obj = {"result": content}
                contents.append({
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name": name,
                            "response": resp_obj
                        }
                    }]
                })
                
        return contents, system_instruction

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

        token = cls.get_token()
        project_id = cls.get_project_id()

        contents, system_instruction = cls.map_messages(messages)
        gemini_tools = cls.map_tools(tools)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            "User-Agent": "antigravity/2.0.0 linux/amd64",
            "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
            "Client-Metadata": '{"ideType":"IDE_UNSPECIFIED","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'
        }

        request_payload = {
            "contents": contents
        }
        if system_instruction:
            request_payload["systemInstruction"] = system_instruction
        if gemini_tools:
            request_payload["tools"] = gemini_tools
        if temperature is not None:
            request_payload["generationConfig"] = {"temperature": temperature}

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
                                tool_calls = []
                                for part in parts:
                                    if "text" in part:
                                        text += part["text"]
                                    if "functionCall" in part:
                                        fc = part["functionCall"]
                                        tool_calls.append(SimpleNamespace(
                                            index=len(tool_calls),
                                            id=fc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                                            type="function",
                                            function=SimpleNamespace(
                                                name=fc.get("name"),
                                                arguments=json.dumps(fc.get("args"))
                                            )
                                        ))
                                
                                delta = SimpleNamespace()
                                if text:
                                    delta.content = text
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
            resp.raise_for_status()
            res_data = resp.json()

            candidate = res_data.get("response", {}).get("candidates", [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            finish_reason = candidate.get("finishReason")

            text = ""
            tool_calls = []
            for part in parts:
                if "text" in part:
                    text += part["text"]
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append({
                        "id": fc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": fc.get("name"),
                            "arguments": json.dumps(fc.get("args"))
                        }
                    })

            choice = {
                "message": {
                    "role": "assistant",
                    "content": text
                },
                "finish_reason": finish_reason
            }
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
            models_list = data.get("models", [])
            
            models = []
            for m in models_list:
                model_id = m.get("modelId")
                if not model_id:
                    continue
                # Asegurar prefijo antigravity/
                if not model_id.startswith("antigravity/"):
                    full_id = f"antigravity/{model_id}"
                else:
                    full_id = model_id
                
                # Nombre descriptivo
                display_name = m.get("displayName", model_id.split("/")[-1])
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
    client_id = base64.b64decode("MTA3MTAwNjA2MDU5MS10bWhzc2luMmgyMWxjcmUyMzV2dG9sb2poNGc0MDNlcC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbQ==").decode()
    client_secret = base64.b64decode("R09DU1BYLUs1OEZXUjQ4NkxkTEoxbUxCOHNYQzR6cURBZg==").decode()
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
