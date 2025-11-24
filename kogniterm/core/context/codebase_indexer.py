from __future__ import annotations
import os
import fnmatch
from typing import List, Dict, Any
from kogniterm.terminal.config_manager import ConfigManager
from kogniterm.core.embeddings_service import EmbeddingsService
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.console import Console
import asyncio
import logging

logger = logging.getLogger(__name__)

class CodebaseIndexer:
    def __init__(self, workspace_directory: str):
        self.workspace_directory = workspace_directory
        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        self.embeddings_service = EmbeddingsService()
        
        exclude_dirs_str = self.config.get("codebase_index_exclude_dirs", "node_modules,.git,__pycache__,.kogniterm")
        self.exclude_dirs = [d.strip() for d in exclude_dirs_str.split(',') if d.strip()]
        
        include_patterns_str = self.config.get("codebase_index_include_patterns", "*.py,*.js,*.ts,*.html,*.css,*.md")
        self.include_patterns = [p.strip() for p in include_patterns_str.split(',') if p.strip()]
        
        self.chunk_size = int(self.config.get("codebase_chunk_size", 1000))
        self.chunk_overlap = int(self.config.get("codebase_chunk_overlap", 100))
        self.console = Console()

    def _should_ignore(self, path: str, is_dir: bool) -> bool:
        """Determines if a file or directory should be ignored."""
        base_name = os.path.basename(path)
        if is_dir and base_name in self.exclude_dirs:
            return True
        if not is_dir and not any(fnmatch.fnmatch(base_name, pattern) for pattern in self.include_patterns):
            return True
        return False

    def list_code_files(self, project_path: str) -> List[str]:
        """Recursively lists code files in the project directory."""
        code_files = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(root, d), is_dir=True)]
            
            for file in files:
                file_path = os.path.join(root, file)
                if not self._should_ignore(file_path, is_dir=False):
                    code_files.append(file_path)
        return code_files

    def chunk_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Reads a file and splits it into logical chunks."""
        chunks = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            current_chunk_content = []
            current_start_line = 1 # 1-indexed

            for i, line in enumerate(lines):
                current_chunk_content.append(line)
                # Simple chunking by character count approximation (or line count)
                # Here we check character count of the chunk
                if len('\n'.join(current_chunk_content)) >= self.chunk_size:
                    chunk_text = '\n'.join(current_chunk_content)
                    chunks.append({
                        'content': chunk_text,
                        'file_path': file_path,
                        'start_line': current_start_line,
                        'end_line': i + 1
                    })
                    
                    # Handle overlap
                    # Calculate how many lines to keep for overlap
                    # This is a simple approximation
                    overlap_text = ""
                    overlap_lines = []
                    for line in reversed(current_chunk_content):
                        if len(overlap_text) + len(line) < self.chunk_overlap:
                            overlap_text = line + "\n" + overlap_text
                            overlap_lines.insert(0, line)
                        else:
                            break
                    
                    current_chunk_content = overlap_lines
                    current_start_line = i + 1 - len(overlap_lines) + 1
            
            if current_chunk_content:
                chunks.append({
                    'content': '\n'.join(current_chunk_content),
                    'file_path': file_path,
                    'start_line': current_start_line,
                    'end_line': len(lines)
                })
        except Exception as e:
            logger.error(f"Error chunking file {file_path}: {e}")
        return chunks

    async def index_project(self, project_path: str) -> List[Dict[str, Any]]:
        """Orchestrates the indexing process."""
        all_chunks = []
        code_files = self.list_code_files(project_path)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            file_indexing_task = progress.add_task("[cyan]Indexing files...", total=len(code_files))
            
            for file_path in code_files:
                progress.update(file_indexing_task, description=f"[cyan]Processing: {os.path.basename(file_path)}")
                file_chunks = await asyncio.to_thread(self.chunk_file, file_path)
                all_chunks.extend(file_chunks)
                progress.advance(file_indexing_task)
            
            if all_chunks:
                embedding_task = progress.add_task("[green]Generating embeddings...", total=len(all_chunks))
                texts_to_embed = [chunk['content'] for chunk in all_chunks]
                
                batch_size = 50 # Smaller batch size to be safe
                embeddings = []
                for i in range(0, len(texts_to_embed), batch_size):
                    batch_texts = texts_to_embed[i:i + batch_size]
                    try:
                        batch_embeddings = await asyncio.to_thread(self.embeddings_service.generate_embeddings, batch_texts)
                        embeddings.extend(batch_embeddings)
                    except Exception as e:
                        logger.error(f"Failed to embed batch {i}: {e}")
                        # Add empty embeddings or handle error?
                        # For now, we might end up with fewer embeddings than chunks if we don't handle this.
                        # But generate_embeddings raises exception, so we probably stop here.
                        raise e
                        
                    progress.advance(embedding_task, advance=len(batch_texts))

                for i, chunk in enumerate(all_chunks):
                    if i < len(embeddings):
                        chunk['embedding'] = embeddings[i]
            
        return all_chunks
