import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Any, Optional
import logging
import uuid

logger = logging.getLogger(__name__)

class VectorDBManager:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.db_path = os.path.join(project_path, ".kogniterm", "vector_db")
        self._ensure_db_dir()
        
        try:
            self.client = chromadb.PersistentClient(path=self.db_path)
            self.collection = self.client.get_or_create_collection(name="codebase_chunks")
        except Exception as e:
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

        ids = [str(uuid.uuid4()) for _ in chunks]
        documents = [chunk['content'] for chunk in chunks]
        embeddings = [chunk['embedding'] for chunk in chunks]
        
        metadatas = []
        for chunk in chunks:
            meta = {
                "file_path": chunk['file_path'],
                "start_line": chunk['start_line'],
                "end_line": chunk['end_line']
            }
            metadatas.append(meta)

        try:
            self.collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Added {len(chunks)} chunks to ChromaDB.")
        except Exception as e:
            logger.error(f"Error adding chunks to ChromaDB: {e}")
            raise e

    def search(self, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """
        Searches for the k most similar chunks to the query embedding.
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k
            )
            
            # Reformat results
            formatted_results = []
            if results['documents']:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if results['distances'] else None
                    })
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching ChromaDB: {e}")
            return []

    def clear_collection(self):
        """Deletes all items in the collection."""
        try:
            # ChromaDB doesn't have a clear method, so we delete and recreate
            self.client.delete_collection("codebase_chunks")
            self.collection = self.client.get_or_create_collection(name="codebase_chunks")
        except Exception as e:
             logger.error(f"Error clearing collection: {e}")
