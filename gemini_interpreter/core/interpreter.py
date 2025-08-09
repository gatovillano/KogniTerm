import os
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from .command_executor import CommandExecutor
import re # Para expresiones regulares

class Interpreter:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("Error: La variable de entorno GOOGLE_API_KEY no está configurada.", file=os.sys.stderr)
            raise ValueError("La variable de entorno GOOGLE_API_KEY no está configurada.")

        genai.configure(api_key=api_key)

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        self.model = genai.GenerativeModel(self.model_name)
        self.executor = CommandExecutor()
        self.messages = [] # Almacena mensajes en el formato {role: "user"|"model", parts: [text]}

        # Mensaje de sistema para instruir a Gemini
        self.system_message = {
            "role": "user",
            "parts": [
                "Eres un asistente experto en terminal Linux. Cuando el usuario te pida realizar una tarea que requiera ejecutar comandos, siempre proporciona una breve introducción conversacional antes del bloque de código. Luego, proporciona el comando(s) en un bloque de código Markdown (```bash\ncomando aquí\n```). Si el usuario hace una pregunta que se puede responder directamente, proporciona la respuesta. No expliques los comandos a menos que se te pida. Solo proporciona un bloque de comando a la vez. Si un comando requiere interacción del usuario (como la contraseña de sudo), explica que se le pedirá al usuario. Después de que un comando se ejecute, se te proporcionará la salida del comando en un bloque de código Markdown con el prefijo 'OUTPUT:'."
            ]
        }
        # Añadir el mensaje de sistema al historial al inicio
        self.messages.append(self.system_message)

    def reset(self):
        # Limpiar el historial de mensajes
        self.messages = []
        # Añadir el mensaje de sistema de nuevo
        self.messages.append(self.system_message)

    def undo(self):
        # Elimina el último mensaje del usuario y la última respuesta del modelo.
        if len(self.messages) > 2: # Asegurarse de no eliminar el mensaje de sistema
            # Eliminar los últimos dos mensajes
            self.messages.pop()
            self.messages.pop()
            return True
        return False

    def chat(self, user_message, add_to_history=True):
        # Construir el historial para la API desde self.messages
        gemini_history = []
        for msg in self.messages:
            if msg["role"] == "user":
                gemini_history.append({"role": "user", "parts": msg["parts"]})
            elif msg["role"] == "model":
                gemini_history.append({"role": "model", "parts": msg["parts"]})

        # Iniciar la sesión de chat con el historial actual
        chat_session = self.model.start_chat(history=gemini_history)

        try:
            # Enviar el nuevo mensaje
            response = chat_session.send_message(user_message)
            
            gemini_response_text = response.text
            
            # Si corresponde, añadir el par de mensajes (usuario y modelo) al historial persistente
            if add_to_history:
                self.messages.append({"role": "user", "parts": [user_message]})
                self.messages.append({"role": "model", "parts": [gemini_response_text]})

            command_to_execute = None
            # Parsear la respuesta de Gemini en busca de bloques de código
            code_block_match = re.search(r"```(?:bash|sh|python|)\
(.*?)\
```", gemini_response_text, re.DOTALL)

            if code_block_match:
                command_to_execute = code_block_match.group(1).strip()
                
            return gemini_response_text, command_to_execute

        except GoogleAPIError as e:
            error_message = f"Error de API de Gemini: {e}"
            print(f"ERROR: {error_message}", file=sys.stderr)
            if add_to_history:
                self.messages.append({"role": "user", "parts": [user_message]})
                self.messages.append({"role": "model", "parts": [error_message]})
            return f"[ERROR]: {error_message}", None
        except Exception as e:
            import traceback
            error_message = f"Ocurrió un error inesperado al comunicarse con Gemini: {e}\
{traceback.format_exc()}"
            print(f"ERROR: {error_message}", file=sys.stderr)
            if add_to_history:
                self.messages.append({"role": "user", "parts": [user_message]})
                self.messages.append({"role": "model", "parts": [error_message]})
            return f"[ERROR]: {error_message}", None

    def add_command_output_to_history(self, command_output):
        # Añadir la salida del comando al historial de mensajes para Gemini
        # Se formatea como un mensaje de usuario para que Gemini lo procese como contexto
        self.messages.append({"role": "user", "parts": [f"OUTPUT:\n```bash\n{command_output}\n```"]})