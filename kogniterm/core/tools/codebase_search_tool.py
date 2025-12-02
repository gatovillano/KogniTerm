from __future__ import annotations
from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from kogniterm.core.embeddings_service import EmbeddingsService
from kogniterm.core.context.vector_db_manager import VectorDBManager
import asyncio
import logging

logger = logging.getLogger(__name__)

class CodebaseSearchToolArgs(BaseModel):
    query: str = Field(..., description="The search query to find relevant code snippets.")
    k: int = Field(5, description="The number of code snippets to return.")
    file_path_filter: Optional[str] = Field(None, description="Optional filter to search only within a specific file path (can be a substring or exact match).")
    language_filter: Optional[str] = Field(None, description="Optional filter to search only within code snippets of a specific programming language (e.g., 'python', 'javascript').")

CodebaseSearchToolArgs.model_rebuild()

class CodebaseSearchTool(BaseTool):
    name: str = "codebase_search"
    description: str = "Searches for relevant code snippets in the project's vector database."
    args_schema: Type[BaseModel] = CodebaseSearchToolArgs

    vector_db_manager: VectorDBManager
    embeddings_service: EmbeddingsService

    def __init__(self, vector_db_manager: VectorDBManager, embeddings_service: EmbeddingsService):
        super().__init__(vector_db_manager=vector_db_manager, embeddings_service=embeddings_service)
        self.vector_db_manager = vector_db_manager
        self.embeddings_service = embeddings_service

    def _run(self, query: str, k: int = 5, file_path_filter: Optional[str] = None, language_filter: Optional[str] = None) -> str:
        """
        Synchronous run method for searching the codebase.
        """
        if not self.vector_db_manager:
            return "Error: VectorDBManager is not initialized. Please index the project first."

        # 1. Generate query embedding
        try:
            logger.info(f"CodebaseSearchTool: Generando embedding para la consulta: '{query}'")
            query_embeddings = self.embeddings_service.generate_embeddings([query])
            logger.info(f"CodebaseSearchTool: Embedding generada (primeros 5 elementos): {query_embeddings[0][:5]}..." if query_embeddings else "No se generó embedding.")
        except Exception as e:
            logger.error(f"CodebaseSearchTool: Error generando embedding para la consulta: {e}")
            return f"Error generando embedding para query: {e}"

        if not query_embeddings:
            logger.warning("CodebaseSearchTool: No se pudo generar embedding para la consulta.")
            return "Error: Could not generate embedding for the query."

        # 2. Search in vector DB
        try:
            logger.info(f"CodebaseSearchTool: Realizando búsqueda en la base de datos vectorial con k={k}, file_path_filter={file_path_filter}, language_filter={language_filter}")
            search_results = self.vector_db_manager.search(
                query_embeddings[0], 
                k=k,
                file_path_filter=file_path_filter,
                language_filter=language_filter
            )
            logger.info(f"CodebaseSearchTool: Resultados de la búsqueda en DB: {len(search_results)} encontrados.")
        except Exception as e:
             logger.error(f"CodebaseSearchTool: Error buscando en la base de datos vectorial: {e}")
             return f"Error searching vector database: {e}"


        # 3. Format results
        if not search_results:
            return "No relevant code snippets found for the query."

        formatted_results = []
        for i, result in enumerate(search_results):
            content = result.get('content', 'Content not available')
            metadata = result.get('metadata', {})
            file_path = metadata.get('file_path', 'Unknown path')
            start_line = metadata.get('start_line', 'N/A')
            end_line = metadata.get('end_line', 'N/A')
            language = metadata.get('language', 'N/A')
            snippet_type = metadata.get('type', 'N/A')
            
            formatted_results.append(
                f"""--- Code Snippet {i+1} ---
File: {file_path}
Lines: {start_line}-{end_line}
Language: {language}
Type: {snippet_type}
Content:
```
{content}
```"""
            )
        
        return "\n".join(formatted_results)
