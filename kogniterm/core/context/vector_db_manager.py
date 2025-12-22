import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Any, Optional
import logging
import uuid

logger = logging.getLogger(__name__)

class VectorDBManager:
    def __init__(self, project_path: str):
        # print(f"DEBUG: VectorDBManager path: {project_path}")
        self.project_path = project_path
        self.db_path = os.path.join(project_path, ".kogniterm", "vector_db")
        # print(f"DEBUG: Asegurando directorio DB en {self.db_path}...")
        self._ensure_db_dir()
        
        try:
            # print("DEBUG: Creando PersistentClient de ChromaDB (sin telemetría)...")
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(anonymized_telemetry=False)
            )
            # print("DEBUG: Obteniendo o creando colección 'codebase_chunks'...")
            self.collection = self.client.get_or_create_collection(name="codebase_chunks")
            # print("DEBUG: ChromaDB inicializado correctamente.")
        except Exception as e:
            # print(f"DEBUG: ERROR en ChromaDB: {e}")
            logger.error(f"Failed to initialize ChromaDB at {self.db_path}: {e}")
            raise e

    def _ensure_db_dir(self):
        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path, exist_ok=True)

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """
        Adds chunks to the vector database.
        Chunks must have 'content', 'embedding', and metadata fields.
        """
        if not chunks:
            return

        batch_size = 5000
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            ids = [str(uuid.uuid4()) for _ in batch]
            documents = [chunk['content'] for chunk in batch]
            embeddings = [chunk['embedding'] for chunk in batch]
            
            metadatas = []
            for chunk in batch:
                meta = {
                    "file_path": chunk['file_path'],
                    "start_line": chunk['start_line'],
                    "end_line": chunk['end_line'],
                    "language": chunk.get('language', 'unknown'),
                    "type": chunk.get('type', 'code_block')
                }
                metadatas.append(meta)

            try:
                self.collection.add(
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                logger.info(f"Added {len(batch)} chunks to ChromaDB (Batch {i//batch_size + 1}).")
            except Exception as e:
                logger.error(f"Error adding chunks to ChromaDB at batch {i//batch_size + 1}: {e}")
                raise e

    def search(self, query_embedding: List[float], k: int = 5, file_path_filter: Optional[str] = None, language_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Searches for similar chunks in the vector database with optional filters."""
        if not self.collection:
            return []
        
        where_clause = {}
        if file_path_filter:
            # Simple substring match for now, or exact match if user provides full path
            # ChromaDB 'where' supports $contains for string fields? No, only exact match or $in, $ne.
            # But we can use $like if supported, or just exact match for now.
            # Wait, ChromaDB allows filtering by metadata fields.
            # If we want glob support, we might need to do post-filtering or use specific operators if available.
            # For now, let's assume exact match or simple contains if we can.
            # Actually, let's just support exact match or use a custom logic if needed.
            # But to keep it simple and robust:
            # If the user provides a filter, we try to match it.
            # ChromaDB 0.4+ supports $contains for document content, but for metadata?
            # Let's stick to exact match for language, and maybe exact match for file_path for now.
            # Or better: The user might want to filter by directory.
            # If we can't do partial match easily in ChromaDB metadata, we might need to fetch more and filter in python.
            # Let's try to use $contains if available, otherwise exact match.
            # Checking ChromaDB docs: Metadata filtering supports $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin.
            # No $contains for metadata strings in standard ChromaDB yet (as of my last knowledge).
            # So we will use exact match for language.
            # For file_path, it's tricky. We might need to fetch more results and filter client-side (here).
            pass 

        # Construct where clause
        conditions = []
        if language_filter:
            conditions.append({"language": language_filter})
        
        # Only add file_path_filter to where_clause if it's an exact match (no wildcards)
        if file_path_filter and '*' not in file_path_filter:
             conditions.append({"file_path": file_path_filter})
        elif file_path_filter and '*' in file_path_filter:
            logger.warning(f"VectorDBManager.search: El filtro de ruta de archivo '{file_path_filter}' contiene comodines ('*') y no puede ser aplicado directamente por ChromaDB. Se ignorará este filtro en la consulta a la DB.")

        if len(conditions) > 1:
            where_clause = {"$and": conditions}
        elif len(conditions) == 1:
            where_clause = conditions[0]
        else:
            where_clause = None # No filters

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k, # No fetch extra results for post-filtering for now
                where=where_clause
            )
            
            formatted_results = []
            if results['documents']:
                for i in range(len(results['documents'][0])):
                    metadata = results['metadatas'][0][i]
                    
                    # No post-filtering for file_path for now.
                    # If file_path_filter was a glob, it was warned and ignored.
                    # If it was an exact match, it was handled by where_clause.

                    formatted_results.append({
                        'content': results['documents'][0][i],
                        'metadata': metadata,
                        'distance': results['distances'][0][i] if results['distances'] else None
                    })
            
            return formatted_results[:k]
            
        except Exception as e:
            logger.error(f"Error searching vector DB: {e}")
            return []

    def clear_collection(self):
        """Deletes all items in the collection."""
        try:
            # ChromaDB doesn't have a clear method, so we delete and recreate
            self.client.delete_collection("codebase_chunks")
            self.collection = self.client.get_or_create_collection(name="codebase_chunks")
        except Exception as e:
             logger.error(f"Error clearing collection: {e}")

    def is_indexed(self) -> bool:
        """Checks if the project is already indexed."""
        try:
            return self.collection.count() > 0
        except Exception:
            return False
