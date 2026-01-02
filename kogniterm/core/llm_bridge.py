from typing import Any, List, Optional, Union, Iterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langchain_core.callbacks import CallbackManagerForLLMRun
import logging

logger = logging.getLogger(__name__)

class KogniChatModel(BaseChatModel):
    """
    Un puente entre LangChain y el LLMService de KogniTerm.
    Permite que CrewAI y otras herramientas de LangChain usen la lógica de 
    validación, fallbacks y parseo de KogniTerm.
    """
    llm_service: Any
    model_name: str
    
    def __init__(self, llm_service: Any, **kwargs):
        super().__init__(llm_service=llm_service, model_name=llm_service.model_name, **kwargs)
        self.llm_service = llm_service
        self.model_name = llm_service.model_name

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Usar el LLMService para invocar al modelo
        # Nota: LLMService.invoke es un generador
        full_content = ""
        final_ai_message = None
        
        # Extraer el system_message si existe en los kwargs o en los mensajes
        system_message = None
        filtered_history = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_message = msg.content
            else:
                filtered_history.append(msg)

        # Invocar a nuestro servicio con toda su lógica de blindaje
        for chunk in self.llm_service.invoke(
            history=filtered_history,
            system_message=system_message,
            save_history=False # No queremos que las llamadas internas de la Crew ensucien el historial global
        ):
            if isinstance(chunk, AIMessage):
                final_ai_message = chunk
            elif isinstance(chunk, str):
                if not chunk.startswith("__THINKING__:"):
                    full_content += chunk
                    if run_manager:
                        run_manager.on_llm_new_token(chunk)
        
        if not final_ai_message:
            final_ai_message = AIMessage(content=full_content)
            
        generation = ChatGeneration(message=final_ai_message)
        return ChatResult(generations=[generation])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        # Implementación de streaming
        system_message = None
        filtered_history = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_message = msg.content
            else:
                filtered_history.append(msg)

        for chunk in self.llm_service.invoke(
            history=filtered_history,
            system_message=system_message,
            save_history=False
        ):
            if isinstance(chunk, str):
                if chunk.startswith("__THINKING__:"):
                    # Omitir thinking en stream por ahora o manejarlo
                    continue
                yield ChatGenerationChunk(message=AIMessage(content=chunk))
            elif isinstance(chunk, AIMessage):
                # Al final, enviamos el mensaje completo con tool_calls si existen
                yield ChatGenerationChunk(message=chunk)

    @property
    def _llm_type(self) -> str:
        return "kogniterm_bridge"

    @property
    def _identifying_params(self) -> Any:
        return {"model_name": self.model_name}
