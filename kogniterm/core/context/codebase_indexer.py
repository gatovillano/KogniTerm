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
        
        # Load ignore patterns
        self.ignore_patterns = self._load_ignore_patterns()

    def _load_ignore_patterns(self) -> List[str]:
        """Loads ignore patterns from .gitignore and .kognitermignore."""
        patterns = []
        for filename in ['.gitignore', '.kognitermignore']:
            file_path = os.path.join(self.workspace_directory, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                patterns.append(line)
                except Exception as e:
                    logger.warning(f"Error reading {filename}: {e}")
        return patterns

    def _matches_ignore_patterns(self, rel_path: str, is_dir: bool) -> bool:
        """Checks if a path matches any of the ignore patterns."""
        import fnmatch
        for pattern in self.ignore_patterns:
            # Handle directory-specific patterns (ending with /)
            if pattern.endswith('/'):
                if is_dir:
                    # Check if directory matches pattern (without slash)
                    pat = pattern.rstrip('/')
                    if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(os.path.basename(rel_path), pat):
                        return True
            else:
                # Standard file/dir pattern
                if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(rel_path), pattern):
                    return True
        return False

    def _should_ignore(self, path: str, is_dir: bool) -> bool:
        """Determines if a file or directory should be ignored."""
        base_name = os.path.basename(path)
        
        # 1. Check explicit exclude dirs (legacy/config)
        if is_dir and base_name in self.exclude_dirs:
            return True
            
        # 2. Check ignore patterns (git/kogniterm ignore)
        rel_path = os.path.relpath(path, self.workspace_directory)
        if self._matches_ignore_patterns(rel_path, is_dir):
            return True

        # 3. Check include patterns (only for files)
        # If it's a file, it MUST match one of the include patterns
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

    def _infer_language(self, file_path: str) -> str:
        """Infers the programming language from the file extension."""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.py': return 'python'
        if ext in ['.js', '.jsx']: return 'javascript'
        if ext in ['.ts', '.tsx']: return 'typescript'
        if ext == '.html': return 'html'
        if ext == '.css': return 'css'
        if ext == '.md': return 'markdown'
        if ext == '.json': return 'json'
        if ext == '.sh': return 'bash'
        if ext == '.sql': return 'sql'
        return 'unknown'

    def chunk_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Reads a file and splits it into logical chunks."""
        chunks = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            language = self._infer_language(file_path)
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
                        'end_line': i + 1,
                        'language': language,
                        'type': 'code_block'
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
                    'end_line': len(lines),
                    'language': language,
                    'type': 'code_block'
                })
        except Exception as e:
            logger.error(f"Error chunking file {file_path}: {e}")
        return chunks

    async def index_project(self, project_path: str, show_progress: bool = True, progress_callback=None) -> List[Dict[str, Any]]:
        """
        Orchestrates the indexing process.
        progress_callback: function(current, total, description)
        """
        all_chunks = []
        code_files = self.list_code_files(project_path)
        total_files = len(code_files)
        
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                file_indexing_task = progress.add_task("[cyan]Indexing files...", total=total_files)
                
                for i, file_path in enumerate(code_files):
                    progress.update(file_indexing_task, description=f"[cyan]Processing: {os.path.basename(file_path)}")
                    
                    # Call callback if provided
                    if progress_callback:
                        progress_callback(i, total_files, f"Indexing: {os.path.basename(file_path)}")
                        
                    file_chunks = await asyncio.to_thread(self.chunk_file, file_path)
                    all_chunks.extend(file_chunks)
                    progress.advance(file_indexing_task)
                
                texts_to_embed = [] # Initialize here
                
                if all_chunks:
                    texts_to_embed = [chunk['content'] for chunk in all_chunks]
                    total_chunks = len(all_chunks)
                    
                    if texts_to_embed: # Only proceed if there are texts to embed
                        embedding_task = progress.add_task("[green]Generando embeddings...", total=len(all_chunks))
                        embeddings = []
                        for i, text in enumerate(texts_to_embed):
                            if progress_callback:
                                progress_callback(i, total_chunks, f"Embedding chunk {i+1}/{total_chunks}")
                            try:
                                # Send one text at a time
                                batch_embeddings = await asyncio.to_thread(self.embeddings_service.generate_embeddings, [text])
                                embeddings.extend(batch_embeddings)
                            except Exception as e:
                                logger.error(f"Failed to embed chunk {i}: {e}")
                                # Instead of raising, we can log and skip this chunk,
                                # but for now, let's re-raise to get immediate feedback.
                                raise e
                            progress.advance(embedding_task, advance=1)
                
                

                    for i, chunk in enumerate(all_chunks):
                        if i < len(embeddings):
                            chunk['embedding'] = embeddings[i]
        else:
            # Silent mode (no progress bar)
            for i, file_path in enumerate(code_files):
                if progress_callback:
                    progress_callback(i, total_files, f"Indexing: {os.path.basename(file_path)}")

                file_chunks = await asyncio.to_thread(self.chunk_file, file_path)
                all_chunks.extend(file_chunks)
            
            texts_to_embed = [] # Initialize here
            if all_chunks:
                texts_to_embed = [chunk['content'] for chunk in all_chunks]
                total_chunks = len(all_chunks)
                
                if texts_to_embed: # Only proceed if there are texts to embed
                    embeddings = []
                    for i, text in enumerate(texts_to_embed):
                        if progress_callback:
                            progress_callback(i, total_chunks, f"Embedding chunk {i+1}/{total_chunks}")
                        try:
                            # Send one text at a time
                            batch_embeddings = await asyncio.to_thread(self.embeddings_service.generate_embeddings, [text])
                            embeddings.extend(batch_embeddings)
                        except Exception as e:
                            logger.error(f"Failed to embed chunk {i}: {e}")
                            raise e

                for i, chunk in enumerate(all_chunks):
                    if i < len(embeddings):
                        chunk['embedding'] = embeddings[i]
            
        # Filter out chunks that don't have a valid embedding
        valid_chunks = [c for c in all_chunks if 'embedding' in c and c['embedding'] and len(c['embedding']) > 0]
        
        if len(valid_chunks) < len(all_chunks):
            logger.warning(f"Skipped {len(all_chunks) - len(valid_chunks)} chunks due to missing or empty embeddings.")
            
        return valid_chunks
