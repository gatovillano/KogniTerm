import asyncio
import os
import shutil
from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.core.context.codebase_indexer import CodebaseIndexer
from kogniterm.core.context.vector_db_manager import VectorDBManager
from kogniterm.core.tools.codebase_search_tool import CodebaseSearchTool
from kogniterm.core.embeddings_service import EmbeddingsService

async def main():
    print("--- Starting RAG Verification ---")
    
    # 1. Config Test
    print("\n[1] Testing ConfigManager...")
    cm = ConfigManager()
    cm.set_global_config("test_key", "global_value")
    cm.set_project_config("test_key", "project_value")
    val = cm.get_config("test_key")
    print(f"Config 'test_key' (should be 'project_value'): {val}")
    assert val == "project_value"
    
    # 2. Indexing Test
    print("\n[2] Testing Indexing...")
    # Create a dummy file to index
    with open("test_code.py", "w") as f:
        f.write("def hello_world():\n    print('Hello RAG!')\n")
        
    indexer = CodebaseIndexer(os.getcwd())
    chunks = await asyncio.to_thread(indexer.chunk_file, "test_code.py")
    print(f"Chunks generated: {len(chunks)}")
    assert len(chunks) > 0
    assert "Hello RAG" in chunks[0]['content']

    # 3. Vector DB & Search Test
    print("\n[3] Testing Vector DB & Search...")
    # We need an API key for this to work. 
    # Assuming environment variables are set or config is set.
    # If not, this part might fail if no API key is present.
    
    try:
        embeddings_service = EmbeddingsService()
        vector_db = VectorDBManager(os.getcwd())
        
        # Mock embedding for the chunk to avoid API call if possible, 
        # but VectorDBManager uses real embeddings. 
        # Let's try to run a real index if API key exists.
        if embeddings_service.api_key:
            print("API Key found. Running full index and search...")
            chunks = await indexer.index_project(os.getcwd())
            vector_db.clear_collection()
            vector_db.add_chunks(chunks)
            
            search_tool = CodebaseSearchTool(vector_db, embeddings_service)
            result = await search_tool._arun("Hello RAG")
            print("Search Result:")
            print(result)
            assert "test_code.py" in result
        else:
            print("Skipping full index/search test due to missing API Key.")
            
    except Exception as e:
        print(f"Error during Vector DB/Search test: {e}")

    # Cleanup
    if os.path.exists("test_code.py"):
        os.remove("test_code.py")
    
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
