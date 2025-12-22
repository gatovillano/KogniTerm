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
        
        exclude_dirs_str = self.config.get("codebase_index_exclude_dirs", "node_modules,.git,__pycache__,.kogniterm,venv,.venv,dist,build,target")
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
        # Standard patterns that should always be ignored if not already covered
        patterns.extend(['.git/', 'node_modules/', '__pycache__/', '.venv/', 'venv/', 'dist/', 'build/'])
        
        for filename in ['.gitignore', '.kognitermignore']:
            file_path = os.path.join(self.workspace_directory, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r') as f:
                        for line in f:
                            # Remove comments and whitespace
                            line = line.split('#')[0].strip()
                            if line:
                                patterns.append(line)
                except Exception as e:
                    logger.warning(f"Error reading {filename}: {e}")
        
        # Remove duplicates while preserving order
        unique_patterns = []
        for p in patterns:
            if p not in unique_patterns:
                unique_patterns.append(p)
        return unique_patterns

    def _matches_ignore_patterns(self, rel_path: str, is_dir: bool) -> bool:
        """Checks if a path matches any of the ignore patterns."""
        import fnmatch
        
        # Normalizar la ruta para comparaciones consistentes
        rel_path = rel_path.replace(os.sep, '/')
        base_name = os.path.basename(rel_path)
        
        for pattern in self.ignore_patterns:
            pattern = pattern.replace(os.sep, '/')
            
            # Ignorar comentarios y líneas vacías
            if not pattern or pattern.startswith('#'):
                continue
                
            # Si el patrón termina en /, aplica a directorios y a todo su contenido
            is_dir_only_pattern = pattern.endswith('/')
            if is_dir_only_pattern:
                pattern = pattern.rstrip('/')

            # Casos de coincidencia:
            # 1. Coincidencia exacta del nombre base (ej: node_modules)
            # 2. Coincidencia con la ruta relativa completa (ej: path/to/file)
            # 3. El archivo está dentro de un directorio que coincide con el patrón (ej: venv/...)
            # 4. Alguna parte de la ruta coincide con el patrón (ej: .../build/...)
            
            if fnmatch.fnmatch(base_name, pattern) or \
               fnmatch.fnmatch(rel_path, pattern) or \
               rel_path.startswith(pattern + '/') or \
               any(fnmatch.fnmatch(part, pattern) for part in rel_path.split('/')):
                
                # Si era un patrón de directorio (terminaba en /), 
                # siempre coincide si llegamos aquí (ya sea porque es el dir o algo dentro)
                if is_dir_only_pattern:
                    return True
                
                # Si no era un patrón de solo directorio, coincide normalmente
                return True
                
        return False

    def _should_ignore(self, path: str, is_dir: bool) -> bool:
        """Determines if a file or directory should be ignored."""
        path = os.path.abspath(path)
        base_name = os.path.basename(path)
        
        # 1. Ignore hidden directories and files by default (starting with .)
        # But allow .kogniterm if explicitly needed (though it's usually in exclude_dirs)
        if base_name.startswith('.') and base_name not in ['.', '..']:
            # Check if it's explicitly allowed (optional future feature)
            if base_name not in ['.gitignore', '.kognitermignore', '.env']:
                return True
        
        # 2. Check explicit exclude dirs (legacy/config)
        if is_dir and base_name in self.exclude_dirs:
            return True
            
        # 3. Check ignore patterns (git/kogniterm ignore)
        try:
            rel_path = os.path.relpath(path, self.workspace_directory)
        except ValueError:
            # Path is on a different drive or something, ignore it
            return True
            
        if self._matches_ignore_patterns(rel_path, is_dir):
            return True

        # 4. Check include patterns (only for files)
        # If it's a file, it MUST match one of the include patterns
        if not is_dir:
            if not any(fnmatch.fnmatch(base_name, pattern) for pattern in self.include_patterns):
                return True
            
        return False

    def list_code_files(self, project_path: str) -> List[str]:
        """Recursively lists code files in the project directory."""
        code_files = []
        project_path = os.path.abspath(project_path)
        
        print(f"\n[DEBUG] Iniciando listado en: {project_path}")
        print(f"[DEBUG] Workspace Dir: {self.workspace_directory}")
        print(f"[DEBUG] Patrones cargados: {self.ignore_patterns}")
        
        found_count = 0
        for root, dirs, files in os.walk(project_path):
            root = os.path.abspath(root)
            
            # Poda de directorios
            dirs_to_keep = []
            for d in dirs:
                dir_path = os.path.join(root, d)
                if not self._should_ignore(dir_path, is_dir=True):
                    dirs_to_keep.append(d)
                else:
                    if found_count < 10: # Solo loguear los primeros para no saturar
                        print(f"[DEBUG] Ignorando directorio: {d}")
            
            dirs[:] = dirs_to_keep
            
            for file in files:
                file_path = os.path.join(root, file)
                if not self._should_ignore(file_path, is_dir=False):
                    code_files.append(file_path)
                    found_count += 1
                    if found_count <= 20:
                        print(f"[DEBUG] ARCHIVO INCLUIDO #{found_count}: {os.path.relpath(file_path, project_path)}")
        
        print(f"[DEBUG] Total archivos encontrados: {len(code_files)}\n")
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
                    progress.update(file_indexing_task, description=f"[cyan]Archivo {i+1}/{total_files}: {os.path.basename(file_path)}")
                    
                    # Call callback if provided
                    if progress_callback:
                        progress_callback(i + 1, total_files, f"Leyendo archivo {i+1}/{total_files}")
                        
                    file_chunks = await asyncio.to_thread(self.chunk_file, file_path)
                    all_chunks.extend(file_chunks)
                    progress.advance(file_indexing_task)
                
                texts_to_embed = []
                
                if all_chunks:
                    texts_to_embed = [chunk['content'] for chunk in all_chunks]
                    total_chunks = len(all_chunks)
                    
                    if texts_to_embed:
                        embedding_task = progress.add_task("[green]Generando embeddings...", total=total_chunks)
                        embeddings = []
                        for i, text in enumerate(texts_to_embed):
                            if progress_callback:
                                progress_callback(i + 1, total_chunks, f"Embedding bloque {i+1}/{total_chunks}")
                            try:
                                batch_embeddings = await asyncio.to_thread(self.embeddings_service.generate_embeddings, [text])
                                embeddings.extend(batch_embeddings)
                            except Exception as e:
                                logger.error(f"Failed to embed chunk {i}: {e}")
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
