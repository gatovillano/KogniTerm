from __future__ import annotations
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from kogniterm.core.embeddings_service import EmbeddingsService
from kogniterm.core.context.vector_db_manager import VectorDBManager
import asyncio

class CodebaseSearchToolArgs(BaseModel):
    query: str = Field(..., description="The search query to find relevant code snippets.")
    k: int = Field(5, description="The number of code snippets to return.")

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

    def _run(self, query: str, k: int = 5) -> str:
        """Synchronous run method, not implemented for this async tool."""
        raise NotImplementedError("CodebaseSearchTool is an async tool, use _arun instead.")

    async def _arun(self, query: str, k: int = 5) -> str:
        """
        Searches for the most relevant code snippets in the project's vector database.

        Args:
            query (str): The search query.
            k (int): The number of results to return.

        Returns:
            str: A formatted string with the found code snippets.
        """
        if not self.vector_db_manager:
            return "Error: VectorDBManager is not initialized. Please index the project first."

        # 1. Generate query embedding
        # generate_embeddings returns a list of lists, we take the first one
        try:
            # Run in thread if it's blocking, but generate_embeddings is sync in our service currently
            # but we can wrap it in to_thread just in case or if we change it later
            query_embeddings = await asyncio.to_thread(self.embeddings_service.generate_embeddings, [query])
        except Exception as e:
            return f"Error generating embedding for query: {e}"

        if not query_embeddings:
            return "Error: Could not generate embedding for the query."

        # 2. Search in vector DB
        try:
            search_results = await asyncio.to_thread(self.vector_db_manager.search, query_embeddings[0], k=k)
        except Exception as e:
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
            
            formatted_results.append(
                f"""--- Code Snippet {i+1} ---
File: {file_path}
Lines: {start_line}-{end_line}
Content:
```
{content}
```"""
            )
        
        return "\n".join(formatted_results)
