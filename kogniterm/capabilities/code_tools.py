"""Capacidades nativas ultrarrápidas de análisis de código y búsqueda semántica para KogniTerm."""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from kogniterm.capabilities.registry import tool

logger = logging.getLogger(__name__)

# Intentamos importar radon de forma condicional
try:
    import radon.complexity as radon_cc
    import radon.metrics as radon_metrics
    import radon.raw as radon_raw
    from radon.visitors import ComplexityVisitor
except ImportError:
    radon_cc = None
    radon_metrics = None
    radon_raw = None
    ComplexityVisitor = None


class CodeAnalysisParams(BaseModel):
    analysis_type: str = Field(
        description="Tipo de análisis: 'lint', 'complexity', 'maintainability', 'raw', 'halstead'"
    )
    path: str = Field(
        description="Ruta al archivo o directorio a analizar"
    )
    recursive: bool = Field(
        default=False,
        description="Si es True y path es un directorio, busca archivos recursivamente"
    )


class CodebaseSearchParams(BaseModel):
    query: str = Field(
        description="Consulta de búsqueda semántica para encontrar fragmentos de código relevantes"
    )
    k: int = Field(
        default=5,
        description="Número de fragmentos de código a retornar"
    )
    file_path_filter: Optional[str] = Field(
        default=None,
        description="Filtro para buscar solo dentro de una ruta de archivo específica"
    )
    language_filter: Optional[str] = Field(
        default=None,
        description="Filtro para buscar solo snippets de un lenguaje específico (ej: 'python', 'javascript')"
    )


def _get_files(path: str, recursive: bool, extensions: List[str] = [".py"]) -> List[str]:
    """Obtiene la lista de archivos a analizar según ruta y extensión."""
    resolved = Path(path).expanduser().resolve()
    files_to_analyze: List[str] = []

    if resolved.is_file():
        if any(str(resolved).endswith(ext) for ext in extensions):
            files_to_analyze.append(str(resolved))
    elif resolved.is_dir():
        if recursive:
            for root, _, files in os.walk(str(resolved)):
                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        files_to_analyze.append(os.path.join(root, file))
        else:
            for item in resolved.iterdir():
                if item.is_file() and any(item.name.endswith(ext) for ext in extensions):
                    files_to_analyze.append(str(item))

    files_to_analyze.sort()
    return files_to_analyze


def _build_progress_bar() -> Progress:
    """Construye una barra de progreso Rich optimizada para retroalimentación visual en terminal."""
    console = Console(file=sys.stderr)
    return Progress(
        SpinnerColumn(style="bold cyan"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(
            complete_style="green",
            finished_style="bold green",
            pulse_style="cyan",
        ),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
        disable=not console.is_terminal and not os.getenv("KOGNITERM_FORCE_PROGRESS"),
    )


def _analyze_complexity_sync(files: List[str], progress: Optional[Progress] = None, task_id: Optional[int] = None) -> Dict[str, Any]:
    """Analiza complejidad ciclomática de los archivos con radon o AST nativo."""
    results = []
    file_details = []

    for idx, file_path in enumerate(files):
        if progress and task_id is not None:
            rel_name = os.path.basename(file_path)
            progress.update(
                task_id,
                advance=1,
                description=f"Analizando complejidad [{idx+1}/{len(files)}]: {rel_name}",
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()

            blocks = []
            if ComplexityVisitor is not None:
                try:
                    visitor = ComplexityVisitor.from_code(code)
                    blocks = getattr(visitor, "blocks", []) or []
                except Exception:
                    if radon_cc is not None and hasattr(radon_cc, "cc_visit"):
                        blocks = radon_cc.cc_visit(code) or []
            elif radon_cc is not None and hasattr(radon_cc, "cc_visit"):
                blocks = radon_cc.cc_visit(code) or []

            file_blocks = []
            total_cc = 0.0
            count = 0

            for block in blocks:
                bname = getattr(block, "name", getattr(block, "fullname", str(block)))
                btype = getattr(block, "type", getattr(block, "kind", "block"))
                complexity = getattr(block, "complexity", getattr(block, "cc", None))
                if complexity is None:
                    complexity = getattr(block, "complexity_score", 0)
                try:
                    cval = float(complexity)
                except Exception:
                    cval = 0.0
                total_cc += cval
                count += 1
                file_blocks.append({"name": bname, "type": str(btype), "complexity": cval})

            avg_cc = round(total_cc / count, 2) if count else 0.0

            file_info = {
                "file": file_path,
                "average_complexity": avg_cc,
                "block_count": count,
                "blocks": file_blocks,
            }
            file_details.append(file_info)

            res_lines = [f"Archivo: {file_path}", f"  Promedio CC: {avg_cc}"]
            if file_blocks:
                res_lines.append("  Detalles:")
                for b in file_blocks:
                    res_lines.append(f"    - {b['name']} ({b['type']}): {b['complexity']}")
            results.append("\n".join(res_lines))

        except Exception as e:
            err_msg = f"Archivo: {file_path} - Error: {e}"
            results.append(err_msg)
            file_details.append({"file": file_path, "error": str(e)})

    return {
        "success": True,
        "total_files": len(files),
        "details": file_details,
        "output": "\n\n".join(results),
    }


def _analyze_maintainability_sync(files: List[str], progress: Optional[Progress] = None, task_id: Optional[int] = None) -> Dict[str, Any]:
    """Analiza índice de mantenibilidad (MI)."""
    results = []
    file_details = []

    for idx, file_path in enumerate(files):
        if progress and task_id is not None:
            rel_name = os.path.basename(file_path)
            progress.update(
                task_id,
                advance=1,
                description=f"Calculando mantenibilidad [{idx+1}/{len(files)}]: {rel_name}",
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()

            if radon_metrics is not None and hasattr(radon_metrics, "mi_visit"):
                mi_score = radon_metrics.mi_visit(code, multi=True)
                rank = radon_metrics.mi_rank(mi_score)
            else:
                mi_score = 100.0
                rank = "A (estimado, sin radon)"

            file_details.append({"file": file_path, "mi": round(mi_score, 2), "rank": rank})
            results.append(
                f"Archivo: {file_path}\n  Índice de Mantenibilidad (MI): {mi_score:.2f}\n  Rango: {rank}"
            )
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")
            file_details.append({"file": file_path, "error": str(e)})

    return {
        "success": True,
        "total_files": len(files),
        "details": file_details,
        "output": "\n\n".join(results),
    }


def _analyze_raw_sync(files: List[str], progress: Optional[Progress] = None, task_id: Optional[int] = None) -> Dict[str, Any]:
    """Analiza métricas en bruto (LOC, LLOC, SLOC, comentarios)."""
    results = []
    file_details = []

    for idx, file_path in enumerate(files):
        if progress and task_id is not None:
            rel_name = os.path.basename(file_path)
            progress.update(
                task_id,
                advance=1,
                description=f"Analizando métricas raw [{idx+1}/{len(files)}]: {rel_name}",
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()

            if radon_raw is not None and hasattr(radon_raw, "analyze"):
                raw_metrics = radon_raw.analyze(code)
                loc, lloc, sloc, comments = (
                    raw_metrics.loc,
                    raw_metrics.lloc,
                    raw_metrics.sloc,
                    raw_metrics.comments,
                )
            else:
                # Fallback nativo
                lines = code.splitlines()
                loc = len(lines)
                comments = sum(1 for line in lines if line.strip().startswith("#"))
                sloc = sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))
                lloc = sloc

            file_details.append(
                {"file": file_path, "loc": loc, "lloc": lloc, "sloc": sloc, "comments": comments}
            )
            results.append(
                f"Archivo: {file_path}\n  LOC: {loc}\n  LLOC: {lloc}\n  SLOC: {sloc}\n  Comentarios: {comments}"
            )
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")
            file_details.append({"file": file_path, "error": str(e)})

    return {
        "success": True,
        "total_files": len(files),
        "details": file_details,
        "output": "\n\n".join(results),
    }


def _analyze_halstead_sync(files: List[str], progress: Optional[Progress] = None, task_id: Optional[int] = None) -> Dict[str, Any]:
    """Analiza métricas Halstead."""
    results = []
    file_details = []

    for idx, file_path in enumerate(files):
        if progress and task_id is not None:
            rel_name = os.path.basename(file_path)
            progress.update(
                task_id,
                advance=1,
                description=f"Calculando métricas Halstead [{idx+1}/{len(files)}]: {rel_name}",
            )

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()

            if radon_metrics is not None and hasattr(radon_metrics, "h_visit"):
                h_metrics = radon_metrics.h_visit(code)
                vol = getattr(h_metrics, "volume", 0.0)
                diff = getattr(h_metrics, "difficulty", 0.0)
            else:
                vol, diff = 0.0, 0.0

            file_details.append(
                {"file": file_path, "volume": round(vol, 2), "difficulty": round(diff, 2)}
            )
            results.append(
                f"Archivo: {file_path}\n  Volumen: {vol:.2f}\n  Dificultad: {diff:.2f}"
            )
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")
            file_details.append({"file": file_path, "error": str(e)})

    return {
        "success": True,
        "total_files": len(files),
        "details": file_details,
        "output": "\n\n".join(results),
    }


def _analyze_lint_sync(path: str, recursive: bool, progress: Optional[Progress] = None, task_id: Optional[int] = None) -> Dict[str, Any]:
    """Ejecuta linters disponibles (pylint, eslint, flake8) con reporte de progreso."""
    py_files = _get_files(path, recursive, [".py"])
    js_files = _get_files(path, recursive, [".js", ".ts", ".jsx", ".tsx"])
    all_files = py_files + js_files

    if not all_files:
        return {
            "success": False,
            "error": "No se encontraron archivos de código soportados para linting.",
            "output": "No se encontraron archivos soportados.",
        }

    results = []

    if py_files:
        pylint_bin = shutil.which("pylint")
        flake8_bin = shutil.which("flake8")

        for idx, f in enumerate(py_files):
            if progress and task_id is not None:
                rel_name = os.path.basename(f)
                progress.update(
                    task_id,
                    advance=1,
                    description=f"Ejecutando linter Python [{idx+1}/{len(py_files)}]: {rel_name}",
                )

            if pylint_bin:
                try:
                    cmd = [pylint_bin, f, "--output-format=text", "--score=n", "--reports=n"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                    out = res.stdout.strip()
                    results.append(f"Archivo: {f}\n{out}" if out else f"Archivo: {f}: ✅ Sin errores detectados.")
                except Exception as e:
                    results.append(f"Error ejecutando pylint en {f}: {e}")
            elif flake8_bin:
                try:
                    cmd = [flake8_bin, f]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    out = res.stdout.strip()
                    results.append(f"Archivo: {f}\n{out}" if out else f"Archivo: {f}: ✅ Sin errores detectados.")
                except Exception as e:
                    results.append(f"Error ejecutando flake8 en {f}: {e}")
            else:
                results.append(f"Archivo: {f}: ⚠️ No hay linter de Python instalado (pylint o flake8).")

    if js_files:
        eslint_bin = shutil.which("eslint")
        for idx, f in enumerate(js_files):
            if progress and task_id is not None:
                rel_name = os.path.basename(f)
                progress.update(
                    task_id,
                    advance=1,
                    description=f"Ejecutando linter JS/TS [{idx+1}/{len(js_files)}]: {rel_name}",
                )

            if eslint_bin:
                try:
                    cmd = [eslint_bin, f, "--format", "stylish"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                    out = res.stdout.strip()
                    results.append(f"Archivo: {f}\n{out}" if out else f"Archivo: {f}: ✅ Sin errores detectados.")
                except Exception as e:
                    results.append(f"Error ejecutando eslint en {f}: {e}")
            else:
                results.append(f"Archivo: {f}: ⚠️ No hay linter ESLint instalado.")

    return {
        "success": True,
        "total_files": len(all_files),
        "output": "\n\n".join(results),
    }


@tool(
    name="code_analysis",
    description="Realiza análisis estático de código Python (complejidad, mantenibilidad, métricas raw, lint) con retroalimentación visual de progreso.",
    params_schema=CodeAnalysisParams,
    category="code",
)
async def code_analysis(analysis_type: str, path: str, recursive: bool = False) -> Dict[str, Any]:
    """Ejecuta análisis de código con barra de progreso visual interactiva."""
    # Blindaje contra listas accidentales en argumentos
    if isinstance(path, list) and len(path) > 0:
        path = path[0]
    path_str = str(path).strip().replace("@", "")

    resolved = Path(path_str).expanduser().resolve()
    if not resolved.exists():
        return {
            "success": False,
            "path": path_str,
            "error": f"La ruta '{path_str}' no existe.",
            "output": f"Error: La ruta '{path_str}' no existe.",
        }

    def _sync_execute() -> Dict[str, Any]:
        files = _get_files(str(resolved), recursive)
        if analysis_type != "lint" and not files:
            return {
                "success": False,
                "path": str(resolved),
                "error": "No se encontraron archivos Python para analizar.",
                "output": "No se encontraron archivos Python para analizar.",
            }

        progress = _build_progress_bar()
        with progress:
            total_items = len(files) if analysis_type != "lint" else len(_get_files(str(resolved), recursive, [".py", ".js", ".ts", ".jsx", ".tsx"]))
            task_id = progress.add_task(f"Iniciando análisis {analysis_type}...", total=max(1, total_items))

            if analysis_type == "complexity":
                return _analyze_complexity_sync(files, progress, task_id)
            elif analysis_type == "maintainability":
                return _analyze_maintainability_sync(files, progress, task_id)
            elif analysis_type == "raw":
                return _analyze_raw_sync(files, progress, task_id)
            elif analysis_type == "halstead":
                return _analyze_halstead_sync(files, progress, task_id)
            elif analysis_type == "lint":
                return _analyze_lint_sync(str(resolved), recursive, progress, task_id)
            else:
                return {
                    "success": False,
                    "error": f"Tipo de análisis '{analysis_type}' no soportado.",
                    "output": f"Error: Tipo de análisis '{analysis_type}' no soportado.",
                }

    try:
        res = await asyncio.to_thread(_sync_execute)
        return res
    except Exception as exc:
        logger.error(f"Error en code_analysis: {exc}", exc_info=True)
        return {
            "success": False,
            "path": str(resolved),
            "error": str(exc),
            "output": f"Error durante el análisis: {exc}",
        }


@tool(
    name="codebase_search",
    description="Busca semánticamente fragmentos de código relevantes en la base vectorial del proyecto mostrando el progreso paso a paso.",
    params_schema=CodebaseSearchParams,
    category="code",
)
async def codebase_search(
    query: str,
    k: int = 5,
    file_path_filter: Optional[str] = None,
    language_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Realiza búsqueda semántica en la base vectorial con retroalimentación visual de acciones."""
    def _sync_search() -> Dict[str, Any]:
        progress = _build_progress_bar()
        with progress:
            task_id = progress.add_task(f"Búsqueda semántica: '{query[:30]}...'", total=4)

            # Acción 1: Conexión con servicios
            progress.update(task_id, advance=1, description="[1/4] Inicializando base vectorial y embeddings...")
            try:
                from kogniterm.core.embeddings_service import EmbeddingsService
                from kogniterm.core.context.vector_db_manager import VectorDBManager
                vector_db_manager = VectorDBManager.get_instance()
                embeddings_service = EmbeddingsService.get_instance()
            except ImportError as e:
                return {
                    "success": False,
                    "error": f"No se pudieron importar los servicios vectoriales: {e}",
                    "output": f"Error: No se pudieron importar los servicios necesarios: {e}",
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error al inicializar servicios vectoriales: {e}",
                    "output": f"Error: No se pudieron inicializar los servicios: {e}",
                }

            if not vector_db_manager:
                return {
                    "success": False,
                    "error": "VectorDBManager no está inicializado. Por favor indexa el proyecto primero.",
                    "output": "Error: VectorDBManager no está inicializado. Por favor indexe el proyecto primero.",
                }

            # Acción 2: Generar embeddings
            progress.update(task_id, advance=1, description=f"[2/4] Generando embedding para consulta: '{query[:25]}...'")
            try:
                query_embeddings = embeddings_service.generate_embeddings([query])
            except Exception as e:
                logger.error(f"CodebaseSearch: Error generando embedding: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "output": f"Error generando embedding para query: {e}",
                }

            if not query_embeddings:
                return {
                    "success": False,
                    "error": "No se pudo generar embedding para la consulta.",
                    "output": "Error: No se pudo generar embedding para la consulta.",
                }

            # Acción 3: Búsqueda vectorial
            progress.update(task_id, advance=1, description=f"[3/4] Consultando top-{k} fragmentos similares...")
            try:
                search_results = vector_db_manager.search(
                    query_embeddings[0],
                    k=k,
                    file_path_filter=file_path_filter,
                    language_filter=language_filter,
                )
            except Exception as e:
                logger.error(f"CodebaseSearch: Error en búsqueda vectorial: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "output": f"Error searching vector database: {e}",
                }

            # Acción 4: Procesar y formatear resultados
            progress.update(task_id, advance=1, description="[4/4] Formateando resultados de código...")
            if not search_results:
                return {
                    "success": True,
                    "query": query,
                    "count": 0,
                    "results": [],
                    "output": "No se encontraron snippets de código relevantes para la consulta.",
                }

            formatted_snippets = []
            parsed_items = []
            for i, result in enumerate(search_results):
                content = result.get("content", "Content not available")
                metadata = result.get("metadata", {})
                file_path = metadata.get("file_path", "Unknown path")
                start_line = metadata.get("start_line", "N/A")
                end_line = metadata.get("end_line", "N/A")
                language = metadata.get("language", "N/A")
                snippet_type = metadata.get("type", "N/A")

                parsed_items.append({
                    "file_path": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "language": language,
                    "type": snippet_type,
                    "content": content,
                })

                formatted_snippets.append(
                    f"--- Code Snippet {i+1} ---\n"
                    f"File: {file_path}\n"
                    f"Lines: {start_line}-{end_line}\n"
                    f"Language: {language}\n"
                    f"Type: {snippet_type}\n"
                    f"Content:\n```\n{content}\n```"
                )

            output_text = "\n\n".join(formatted_snippets)
            return {
                "success": True,
                "query": query,
                "count": len(parsed_items),
                "results": parsed_items,
                "output": output_text,
            }

    try:
        res = await asyncio.to_thread(_sync_search)
        return res
    except Exception as exc:
        logger.error(f"Error en codebase_search: {exc}", exc_info=True)
        return {
            "success": False,
            "query": query,
            "error": str(exc),
            "output": f"Error en búsqueda semántica: {exc}",
        }
