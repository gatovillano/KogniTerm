import asyncio
import os
from typing import Type, Optional
from pydantic import BaseModel, Field, SecretStr
from langchain_core.tools import BaseTool
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.summarize import load_summarize_chain
from langchain.schema import Document
import logging
import json # Importar json

logger = logging.getLogger(__name__)

class MemorySummarizeTool(BaseTool):
    name: str = "memory_summarize_tool"
    description: str = "Resume el contenido del historial de memoria persistente si excede un umbral de tokens."

    class MemorySummarizeInput(BaseModel):
        filename: str = Field(default="llm_context.json", description="El nombre del archivo de memoria (por defecto 'llm_context.json').")
        max_tokens: int = Field(default=4000, description="El número máximo de tokens antes de activar el resumen.")
        llm_model_name: str = Field(default="gemini-1.5-flash", description="El nombre del modelo LLM a usar para el resumen.")
        llm_api_key: Optional[SecretStr] = Field(default=None, description="La clave API del LLM para el resumen.")

    args_schema: Type[BaseModel] = MemorySummarizeInput

    def _run(self, filename: str = "llm_context.json", max_tokens: int = 4000, llm_model_name: str = "gemini-1.5-flash", llm_api_key: Optional[SecretStr] = None) -> str:
        logger.debug(f"MemorySummarizeTool - Intentando resumir memoria desde '{filename}'")
        try:
            path = os.path.join(os.getcwd(), filename)
            
            if not os.path.exists(path):
                return f"Memoria '{filename}' no encontrada. No se puede resumir."

            history = FileChatMessageHistory(file_path=path)
            
            # LangChain messages can have content as str or list of dicts (for tool calls).
            # We need to extract only string content for summarization.
            string_contents = []
            for msg in history.messages:
                if isinstance(msg.content, str):
                    string_contents.append(msg.content)
                elif isinstance(msg.content, list): # Handle tool messages or multi-part content
                    for part in msg.content:
                        if isinstance(part, dict) and 'text' in part:
                            string_contents.append(part['text'])
                        elif isinstance(part, str):
                            string_contents.append(part)
            full_content = "\n".join(string_contents)

            # Simple estimación de tokens (aproximada, idealmente usar tiktoken o similar)
            # Para una estimación más precisa con modelos de Google, se necesitaría la API de conteo de tokens.
            # Por ahora, una heurística simple de 4 caracteres por token.
            current_tokens = len(full_content) // 4

            if current_tokens < max_tokens:
                return f"Memoria actual ({current_tokens} tokens) está por debajo del umbral de resumen ({max_tokens} tokens). No se requiere acción."

            logger.info(f"Memoria excede el umbral. Resumiendo de {current_tokens} tokens...")

            # Inicializar LLM para resumen
            # Se usa ChatGoogleGenerativeAI, si es OpenAI, se debe cambiar a ChatOpenAI
            if llm_model_name.startswith("gpt"): # Asumiendo que los modelos de OpenAI empiezan con "gpt"
                from langchain_community.chat_models import ChatOpenAI
                llm = ChatOpenAI(model=llm_model_name, api_key=llm_api_key.get_secret_value() if llm_api_key else None)
            else:
                llm = ChatGoogleGenerativeAI(model=llm_model_name, google_api_key=llm_api_key.get_secret_value() if llm_api_key else None)


            # Cargar cadena de resumen
            chain = load_summarize_chain(llm, chain_type="stuff") # "stuff" es simple, "map_reduce" para más grandes

            # Convertir el historial a Documentos para la cadena de resumen
            docs = [Document(page_content=full_content)]
            summary = chain.run(docs)

            # Sobrescribir el archivo de memoria con el resumen
            with open(path, 'w') as f:
                f.write(json.dumps([{"type": "human", "data": {"content": summary, "additional_kwargs": {}, "example": False}}]) + "\n") # Guardar como un solo mensaje humano resumido
            
            logger.info(f"Memoria resumida exitosamente. Nuevo contenido: {summary[:100]}...")
            return f"Memoria resumida exitosamente. El historial fue compactado."
        except Exception as e:
            logger.error(f"Error inesperado en MemorySummarizeTool al resumir '{filename}': {e}", exc_info=True)
            return f"Error inesperado en MemorySummarizeTool: {e}. Por favor, revisa los logs para más detalles."

    async def _arun(self, filename: str = "llm_context.json", max_tokens: int = 4000, llm_model_name: str = "gemini-1.5-flash", llm_api_key: Optional[SecretStr] = None) -> str:
        return await asyncio.to_thread(self._run, filename, max_tokens, llm_model_name, llm_api_key)