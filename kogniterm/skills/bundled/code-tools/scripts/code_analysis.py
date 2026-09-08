"""
Code Analysis Skill - Análisis estático de código Python.

Provee funcionalidad para analizar código Python con métricas de calidad
y retroalimentación visual mediante barra de progreso interactiva (Rich).
"""

import os
import sys
import logging
import subprocess
import shutil
from typing import Generator, List, Optional
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

# Intentamos importar radon, si falla, lo manejaremos en tiempo de ejecución
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

logger = logging.getLogger(__name__)

# Metadata de la herramienta
name = "code_analysis"
description = "Realiza análisis estático de código Python utilizando la librería 'radon'. Permite calcular Complejidad Ciclomática, Índice de Mantenibilidad y métricas 'raw'."


def _build_progress_bar(console: Optional[Console] = None) -> Progress:
    """Construye una barra de progreso Rich optimizada idéntica a la mostrada en los logs del servidor."""
    if console is None:
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


def code_analysis(analysis_type: str, path: str, recursive: bool = False) -> Generator[str, None, None]:
    """
    Realiza análisis estático de código Python con retroalimentación visual de progreso.

    Args:
        analysis_type: Tipo de análisis: 'lint', 'complexity', 'maintainability', 'raw', 'halstead'
        path: Ruta al archivo o directorio a analizar
        recursive: Si es True y path es un directorio, busca archivos recursivamente

    Yields:
        str: Resultados del análisis
    """
    yield code_analysis_sync(analysis_type, path, recursive)


def _get_files(path: str, recursive: bool, extensions: list = ['.py']) -> list:
    """Obtiene lista de archivos para analizar."""
    files_to_analyze = []
    if os.path.isfile(path):
        if any(path.endswith(ext) for ext in extensions):
            files_to_analyze.append(path)
    elif os.path.isdir(path):
        if recursive:
            for root, _, files in os.walk(path):
                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        files_to_analyze.append(os.path.join(root, file))
        else:
            for file in os.listdir(path):
                full_path = os.path.join(path, file)
                if os.path.isfile(full_path) and any(file.endswith(ext) for ext in extensions):
                    files_to_analyze.append(full_path)
    return files_to_analyze


def _analyze_complexity(
    path: str,
    recursive: bool,
    progress: Optional[Progress] = None,
    task_id: Optional[int] = None,
) -> str:
    """Analiza complejidad ciclomática con reporte de progreso."""
    files = _get_files(path, recursive)
    if not files:
        return "No se encontraron archivos Python para analizar."

    results = []
    for idx, file_path in enumerate(files):
        if progress and task_id is not None:
            rel_name = os.path.basename(file_path)
            progress.update(
                task_id,
                advance=1,
                description=f"Analizando complejidad [{idx+1}/{len(files)}]: {rel_name}",
            )

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                code = f.read()

            blocks = []
            if ComplexityVisitor is not None:
                try:
                    visitor = ComplexityVisitor.from_code(code)
                    blocks = getattr(visitor, "blocks", []) or []
                except Exception:
                    if radon_cc is not None and hasattr(radon_cc, "cc_visit"):
                        blocks = radon_cc.cc_visit(code) or []
            else:
                if radon_cc is not None and hasattr(radon_cc, "cc_visit"):
                    blocks = radon_cc.cc_visit(code) or []

            file_results = []
            total = 0.0
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
                total += cval
                count += 1
                file_results.append(f"    - {bname} ({btype}): {cval}")

            avg_val = total / count if count else 0.0

            results.append(f"Archivo: {file_path}")
            results.append(f"  Promedio CC: {avg_val:.2f}")
            if file_results:
                results.append("  Detalles:")
                results.extend(file_results)
            results.append("")
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")

    return "\n".join(results)


def _analyze_maintainability(
    path: str,
    recursive: bool,
    progress: Optional[Progress] = None,
    task_id: Optional[int] = None,
) -> str:
    """Analiza índice de mantenibilidad con reporte de progreso."""
    files = _get_files(path, recursive)
    if not files:
        return "No se encontraron archivos Python para analizar."

    results = []
    for idx, file_path in enumerate(files):
        if progress and task_id is not None:
            rel_name = os.path.basename(file_path)
            progress.update(
                task_id,
                advance=1,
                description=f"Calculando mantenibilidad [{idx+1}/{len(files)}]: {rel_name}",
            )

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                code = f.read()

            if radon_metrics is not None and hasattr(radon_metrics, "mi_visit"):
                mi_score = radon_metrics.mi_visit(code, multi=True)
                rank = radon_metrics.mi_rank(mi_score)
            else:
                mi_score = 100.0
                rank = "A (estimado, sin radon)"

            results.append(f"Archivo: {file_path}")
            results.append(f"  Índice de Mantenibilidad (MI): {mi_score:.2f}")
            results.append(f"  Rango: {rank}")
            results.append("")
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")

    return "\n".join(results)


def _analyze_raw(
    path: str,
    recursive: bool,
    progress: Optional[Progress] = None,
    task_id: Optional[int] = None,
) -> str:
    """Analiza métricas raw (líneas, comentarios, etc.) con reporte de progreso."""
    files = _get_files(path, recursive)
    if not files:
        return "No se encontraron archivos Python para analizar."

    results = []
    for idx, file_path in enumerate(files):
        if progress and task_id is not None:
            rel_name = os.path.basename(file_path)
            progress.update(
                task_id,
                advance=1,
                description=f"Analizando métricas raw [{idx+1}/{len(files)}]: {rel_name}",
            )

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
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
                lines = code.splitlines()
                loc = len(lines)
                comments = sum(1 for l in lines if l.strip().startswith("#"))
                sloc = sum(1 for l in lines if l.strip() and not l.strip().startswith("#"))
                lloc = sloc

            results.append(f"Archivo: {file_path}")
            results.append(f"  LOC: {loc}")
            results.append(f"  LLOC: {lloc}")
            results.append(f"  SLOC: {sloc}")
            results.append(f"  Comentarios: {comments}")
            results.append("")
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")

    return "\n".join(results)


def _analyze_halstead(
    path: str,
    recursive: bool,
    progress: Optional[Progress] = None,
    task_id: Optional[int] = None,
) -> str:
    """Analiza métricas Halstead con reporte de progreso."""
    files = _get_files(path, recursive)
    if not files:
        return "No se encontraron archivos Python para analizar."

    results = []
    for idx, file_path in enumerate(files):
        if progress and task_id is not None:
            rel_name = os.path.basename(file_path)
            progress.update(
                task_id,
                advance=1,
                description=f"Analizando Halstead [{idx+1}/{len(files)}]: {rel_name}",
            )

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                code = f.read()

            if radon_metrics is not None and hasattr(radon_metrics, "h_visit"):
                h_metrics = radon_metrics.h_visit(code)
                vol = getattr(h_metrics, "volume", 0.0)
                diff = getattr(h_metrics, "difficulty", 0.0)
            else:
                vol, diff = 0.0, 0.0

            results.append(f"Archivo: {file_path}")
            results.append(f"  Volumen: {vol:.2f}")
            results.append(f"  Dificultad: {diff:.2f}")
            results.append("")
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")

    return "\n".join(results)


def _analyze_lint(
    path: str,
    recursive: bool,
    progress: Optional[Progress] = None,
    task_id: Optional[int] = None,
) -> str:
    """Realiza análisis de linting con reporte de progreso interactivo."""
    py_files = _get_files(path, recursive, ['.py'])
    js_files = _get_files(path, recursive, ['.js', '.ts', '.jsx', '.tsx'])

    results = []

    if py_files:
        pylint_bin = shutil.which('pylint')
        flake8_bin = shutil.which('flake8')
        if pylint_bin or flake8_bin:
            results.append("--- Análisis Python Lint ---")
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
                        cmd = [pylint_bin, f, '--output-format=text', '--score=n', '--reports=n']
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                        output = result.stdout.strip()
                        if output:
                            results.append(f"Archivo: {f}\n{output}\n")
                        else:
                            results.append(f"Archivo: {f}: ✅ Sin errores detectados.\n")
                    except Exception as e:
                        results.append(f"Error ejecutando pylint en {f}: {e}")
                elif flake8_bin:
                    try:
                        cmd = [flake8_bin, f]
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                        output = result.stdout.strip()
                        if output:
                            results.append(f"Archivo: {f}\n{output}\n")
                        else:
                            results.append(f"Archivo: {f}: ✅ Sin errores detectados.\n")
                    except Exception as e:
                        results.append(f"Error ejecutando flake8 en {f}: {e}")
        else:
            results.append("⚠️ Advertencia: Ni 'pylint' ni 'flake8' fueron encontrados.")

    if js_files:
        eslint_bin = shutil.which('eslint')
        if eslint_bin:
            results.append("--- Análisis ESLint (JS/TS) ---")
            for idx, f in enumerate(js_files):
                if progress and task_id is not None:
                    rel_name = os.path.basename(f)
                    progress.update(
                        task_id,
                        advance=1,
                        description=f"Ejecutando linter JS/TS [{idx+1}/{len(js_files)}]: {rel_name}",
                    )
                try:
                    cmd = [eslint_bin, f, '--format', 'stylish']
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                    output = result.stdout.strip()
                    if output:
                        results.append(f"Archivo: {f}\n{output}\n")
                    else:
                        results.append(f"Archivo: {f}: ✅ Sin errores detectados.\n")
                except Exception as e:
                    results.append(f"Error ejecutando eslint en {f}: {e}")
        else:
            results.append("⚠️ Advertencia: 'eslint' no encontrado.")

    if not results:
        return "No se encontraron archivos soportados o herramientas de linting instaladas."

    return "\n".join(results)


# Función de compatibilidad para ejecución síncrona
def code_analysis_sync(analysis_type: str, path: str, recursive: bool = False) -> str:
    """
    Versión síncrona de code_analysis con soporte para capability nativa y barra de progreso.
    Retorna el resultado completo como string formateado.
    """
    # 1. Intentar delegar a la Capability nativa
    try:
        import asyncio
        from kogniterm.capabilities.code_tools import code_analysis as cap_code_analysis

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()

        result = loop.run_until_complete(
            cap_code_analysis(analysis_type=analysis_type, path=path, recursive=recursive)
        )
        if isinstance(result, dict):
            return result.get("output", str(result))
        return str(result)
    except Exception as exc:
        logger.debug(f"Delegación a Capability falló o no disponible: {exc}, ejecutando localmente")

    # 2. Fallback / ejecución local autónoma con barra de progreso Rich
    if isinstance(path, list) and len(path) > 0:
        path = path[0]
    path_str = str(path).strip().replace("@", "")

    if not os.path.exists(path_str):
        return f"Error: La ruta '{path_str}' no existe."

    files = _get_files(path_str, recursive)
    total_items = len(files) if analysis_type != "lint" else len(_get_files(path_str, recursive, [".py", ".js", ".ts", ".jsx", ".tsx"]))

    if analysis_type != "lint" and not files:
        return "No se encontraron archivos Python para analizar."

    progress = _build_progress_bar()
    with progress:
        task_id = progress.add_task(f"Iniciando análisis {analysis_type}...", total=max(1, total_items))
        if analysis_type == "complexity":
            return _analyze_complexity(path_str, recursive, progress, task_id)
        elif analysis_type == "maintainability":
            return _analyze_maintainability(path_str, recursive, progress, task_id)
        elif analysis_type == "raw":
            return _analyze_raw(path_str, recursive, progress, task_id)
        elif analysis_type == "halstead":
            return _analyze_halstead(path_str, recursive, progress, task_id)
        elif analysis_type == "lint":
            return _analyze_lint(path_str, recursive, progress, task_id)
        else:
            return f"Error: Tipo de análisis '{analysis_type}' no soportado."


def get_action_description(analysis_type: str = "lint", path: str = ".", **kwargs) -> str:
    """Devuelve una descripción legible de la acción que realiza la herramienta."""
    return f"Analizando código ({analysis_type}) en '{path}'..."


# Asignar explícitamente para compatibilidad con SkillManager
code_analysis.get_action_description = get_action_description


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "analysis_type": {
            "type": "string",
            "description": "Tipo de análisis: 'lint', 'complexity', 'maintainability', 'raw', 'halstead'"
        },
        "path": {
            "type": "string",
            "description": "Ruta al archivo o directorio a analizar"
        },
        "recursive": {
            "type": "boolean",
            "description": "Si es True y path es un directorio, busca archivos recursivamente",
            "default": False
        }
    },
    "required": ["analysis_type", "path"]
}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Realiza análisis estático de código Python (complejidad, mantenibilidad, métricas raw, lint) con retroalimentación visual de progreso."
    )
    parser.add_argument(
        "analysis_type",
        nargs="?",
        default="lint",
        choices=["lint", "complexity", "maintainability", "raw", "halstead"],
        help="Tipo de análisis: 'lint', 'complexity', 'maintainability', 'raw', 'halstead' (por defecto: lint)"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Ruta al archivo o directorio a analizar (por defecto: .)"
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Si es True y path es un directorio, busca archivos recursivamente"
    )
    args = parser.parse_args()

    res = code_analysis_sync(args.analysis_type, args.path, args.recursive)
    print(res)

