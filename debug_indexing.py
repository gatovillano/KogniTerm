import asyncio
import os
import logging
from kogniterm.core.context.codebase_indexer import CodebaseIndexer

logging.basicConfig(level=logging.INFO)

async def main():
    workspace = os.getcwd()
    print(f"Checking workspace: {workspace}")
    # Mock EmbeddingsService to avoid ImportError
    import sys
    from unittest.mock import MagicMock
    mock_embeddings = MagicMock()
    sys.modules['kogniterm.core.embeddings_service'] = MagicMock()
    
    indexer = CodebaseIndexer(workspace)
    files = indexer.list_code_files(workspace)
    print(f"Found {len(files)} files to index.")
    for f in files[:10]:
        print(f" - {os.path.relpath(f, workspace)}")
    if len(files) > 10:
        print(f" ... and {len(files) - 10} more.")

if __name__ == "__main__":
    asyncio.run(main())
