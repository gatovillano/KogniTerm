
import logging
from typing import List, Dict, Tuple, Optional, Callable
from pathlib import Path
import math # Para la similitud coseno

# Asumimos que tienes una forma de obtener embeddings.
# Esto podría ser una API externa (ej. OpenAI) o un modelo local (ej. Sentence Transformers).
# Por simplicidad, aquí usaremos un placeholder.
# from sentence_transformers import SentenceTransformer # Si usas un modelo local
# from openai import OpenAI # Si usas API de OpenAI

logger = logging.getLogger(__name__)

class ContextIndexer:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.index: Dict[str, List[float]] = {} # {file_path: embedding_vector}
        # self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2') # Ejemplo de modelo local
        # self.openai_client = OpenAI() # Ejemplo de cliente OpenAI
        logger.info("ContextIndexer inicializado.")

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Genera un embedding para el texto dado.
        (Placeholder - reemplazar con tu implementación real de embedding)
        """
        # Ejemplo con OpenAI (requiere clave API)
        # response = await self.openai_client.embeddings.create(
        #     input=text,
        #     model="text-embedding-ada-002"
        # )
        # return response.data[0].embedding

        # Ejemplo con Sentence Transformers (modelo local)
        # return self.embedding_model.encode(text).tolist()

        # Simulación de embedding: generar un vector numérico a partir del texto
        # Esto es un placeholder funcional para demostrar el concepto sin dependencias externas.
        # En una implementación real, se usaría un modelo de embedding (ej. Sentence Transformers, OpenAI).
        hash_value = hash(text)
        # Crear un vector de 128 dimensiones basado en el hash
        embedding = [(hash_value % (i + 1)) / 1000.0 for i in range(128)]
        return embedding

    async def index_file(self, file_path: Path, content: str):
        """Indexa un archivo generando su embedding y almacenándolo."""
        if not content:
            self.remove_from_index(file_path) # Eliminar si el contenido está vacío
            return
        embedding = await self._get_embedding(content)
        self.index[str(file_path)] = embedding
        logger.debug(f"Archivo indexado: {file_path}")

    def remove_from_index(self, file_path: Path):
        """Elimina un archivo del índice."""
        if str(file_path) in self.index:
            del self.index[str(file_path)]
            logger.debug(f"Archivo eliminado del índice: {file_path}")

    async def update_index_for_files(self, file_paths: List[Path], file_reader_func: Callable[[str], Optional[str]]):
        """Actualiza el índice para una lista de archivos."""
        for file_path_obj in file_paths:
            file_path_str = str(file_path_obj)
            content = await file_reader_func(file_path_str) # file_reader_func espera str
            if content:
                await self.index_file(file_path_obj, content)
            else:
                self.remove_from_index(file_path_obj) # Eliminar si no se puede leer o está vacío

    async def search_relevant_files(self, query: str, top_k: int = 5) -> List[Tuple[Path, float]]:
        """
        Busca los archivos más relevantes basándose en la similitud semántica con la consulta.
        Devuelve una lista de (Path, score).
        """
        if not self.index:
            return []

        query_embedding = await self._get_embedding(query)
        
        def cosine_similarity(vec1, vec2):
            dot_product = sum(v1 * v2 for v1, v2 in zip(vec1, vec2))
            magnitude1 = math.sqrt(sum(v1**2 for v1 in vec1))
            magnitude2 = math.sqrt(sum(v2**2 for v2 in vec2))
            if not magnitude1 or not magnitude2:
                return 0.0
            return dot_product / (magnitude1 * magnitude2)

        similarities: List[Tuple[Path, float]] = []
        for file_path_str, file_embedding in self.index.items():
            score = cosine_similarity(query_embedding, file_embedding)
            similarities.append((Path(file_path_str), score))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
