"""
Code Analysis Skill - Análisis estático de código Python.

Esta es una skill migrada desde code_analysis_tool.py.
Provee funcionalidad para analizar código Python con métricas de calidad.
"""

import os
import logging
import subprocess
import shutil
from typing import Generator

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


def code_analysis(analysis_type: str, path: str, recursive: bool = False) -> Generator[str, None, None]:
    """
    Realiza análisis estático de código Python.

    Args:
        analysis_type: Tipo de análisis: 'lint', 'complexity', 'maintainability', 'raw', 'halstead'
        path: Ruta al archivo o directorio a analizar
        recursive: Si es True y path es un directorio, busca archivos recursivamente

    Yields:
        str: Resultados del análisis

    Raises:
        Exception: Errores durante el análisis
    """
    # Blindaje contra argumentos tipo lista (error común de LLMs)
    if isinstance(path, list) and len(path) > 0:
        path = path[0]
    
    if not isinstance(path, str):
        path = str(path)

    path = path.strip().replace('@', '')
    if not os.path.exists(path):
        yield f"Error: La ruta '{path}' no existe."
        return

    if radon_cc is None:
        yield "Error: La librería 'radon' no está instalada. Por favor instálala con `pip install radon`."
        return

    try:
        if analysis_type == 'complexity':
            yield _analyze_complexity(path, recursive)
        elif analysis_type == 'maintainability':
            yield _analyze_maintainability(path, recursive)
        elif analysis_type == 'raw':
            yield _analyze_raw(path, recursive)
        elif analysis_type == 'halstead':
            yield _analyze_halstead(path, recursive)
        elif analysis_type == 'lint':
            yield _analyze_lint(path, recursive)
        else:
            yield f"Error: Tipo de análisis '{analysis_type}' no soportado."
    except Exception as e:
        logger.error(f"Error en análisis de código: {e}")
        yield f"Error durante el análisis: {str(e)}"


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


def _analyze_complexity(path: str, recursive: bool) -> str:
    """Analiza complejidad ciclomática."""
    files = _get_files(path, recursive)
    if not files:
        return "No se encontraron archivos Python para analizar."

    results = []
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Usamos ComplexityVisitor si está disponible; si falla o no existe, intentamos cc_visit
            blocks = []
            if ComplexityVisitor is not None:
                try:
                    visitor = ComplexityVisitor.from_code(code)
                    blocks = getattr(visitor, "blocks", []) or []
                except Exception:
                    # si ComplexityVisitor falla, intentar cc_visit si está disponible
                    if radon_cc is not None and hasattr(radon_cc, "cc_visit"):
                        blocks = radon_cc.cc_visit(code) or []
                    else:
                        blocks = []
            else:
                # Si no hay ComplexityVisitor, usar cc_visit solo si radon_cc lo proporciona
                if radon_cc is not None and hasattr(radon_cc, "cc_visit"):
                    blocks = radon_cc.cc_visit(code) or []
                else:
                    blocks = []
 
            file_results = []
            # Los objetos pueden diferir según la API usada; acceder defensivamente
            total = 0.0
            count = 0
            for block in blocks:
                name = getattr(block, "name", getattr(block, "fullname", str(block)))
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
                file_results.append(f"    - {name} ({btype}): {cval}")

            avg_val = total / count if count else 0.0

            results.append(f"Archivo: {file_path}")
            results.append(f"  Promedio CC: {avg_val:.2f}")
            if file_results:
                results.append("  Detalles:")
                results.extend(file_results)
            else:
                results.append("  (Sin bloques analizable)")
            results.append("")
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")
 
    return "\n".join(results)


def _analyze_maintainability(path: str, recursive: bool) -> str:
    """Analiza índice de mantenibilidad."""
    files = _get_files(path, recursive)
    if not files:
        return "No se encontraron archivos Python para analizar."

    results = []
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            mi_score = radon_metrics.mi_visit(code, multi=True)
            rank = radon_metrics.mi_rank(mi_score)
            
            results.append(f"Archivo: {file_path}")
            results.append(f"  Índice de Mantenibilidad (MI): {mi_score:.2f}")
            results.append(f"  Rango: {rank}")
            results.append("")
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")

    return "\n".join(results)


def _analyze_raw(path: str, recursive: bool) -> str:
    """Analiza métricas raw (líneas, comentarios, etc.)."""
    files = _get_files(path, recursive)
    if not files:
        return "No se encontraron archivos Python para analizar."

    results = []
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            raw_metrics = radon_raw.analyze(code)
            
            results.append(f"Archivo: {file_path}")
            results.append(f"  LOC (Líneas de Código): {raw_metrics.loc}")
            results.append(f"  LLOC (Líneas Lógicas): {raw_metrics.lloc}")
            results.append(f"  SLOC (Líneas Fuente): {raw_metrics.sloc}")
            results.append(f"  Comentarios: {raw_metrics.comments}")
            results.append(f"  Multi-line strings: {raw_metrics.multi}")
            results.append(f"  Blancos: {raw_metrics.blank}")
            results.append("")
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")

    return "\n".join(results)


def _analyze_halstead(path: str, recursive: bool) -> str:
    """Analiza métricas Halstead."""
    files = _get_files(path, recursive)
    if not files:
        return "No se encontraron archivos Python para analizar."

    results = []
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            h_metrics = radon_metrics.h_visit(code)
            
            results.append(f"Archivo: {file_path}")
            results.append(f"  Volumen: {h_metrics.volume:.2f}")
            results.append(f"  Dificultad: {h_metrics.difficulty:.2f}")
            results.append(f"  Esfuerzo: {h_metrics.effort:.2f}")
            results.append(f"  Tiempo estimado: {h_metrics.time:.2f} seg")
            results.append(f"  Bugs estimados: {h_metrics.bugs:.2f}")
            results.append("")
        except Exception as e:
            results.append(f"Archivo: {file_path} - Error: {e}")

    return "\n".join(results)


def _analyze_lint(path: str, recursive: bool) -> str:
    """Realiza análisis de linting."""
    py_files = _get_files(path, recursive, ['.py'])
    js_files = _get_files(path, recursive, ['.js', '.ts', '.jsx', '.tsx'])
    
    results = []
    
    # Python Linting
    if py_files:
        if shutil.which('pylint'):
            results.append("--- Análisis Pylint (Python) ---")
            for f in py_files:
                try:
                    # Ejecutar pylint
                    # --output-format=text: formato legible
                    # --score=n: no mostrar puntuación final, solo errores
                    # --reports=n: no mostrar reportes estadísticos
                    cmd = ['pylint', f, '--output-format=text', '--score=n', '--reports=n']
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    output = result.stdout.strip()
                    if output:
                        results.append(f"Archivo: {f}\n{output}\n")
                    elif result.stderr.strip():
                         results.append(f"Archivo: {f} (Error ejecución): {result.stderr.strip()}\n")
                    else:
                         results.append(f"Archivo: {f}: ✅ Sin errores detectados.\n")
                except Exception as e:
                    results.append(f"Error ejecutando pylint en {f}: {e}")
        else:
            results.append("⚠️ Advertencia: 'pylint' no encontrado. Instálalo con 'pip install pylint' para análisis de Python.")

    # JS Linting
    if js_files:
         if shutil.which('eslint'):
            results.append("--- Análisis ESLint (JavaScript/TypeScript) ---")
            for f in js_files:
                try:
                    cmd = ['eslint', f, '--format', 'stylish']
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    output = result.stdout.strip()
                    if output:
                        results.append(f"Archivo: {f}\n{output}\n")
                    elif result.stderr.strip():
                         results.append(f"Archivo: {f} (Error ejecución): {result.stderr.strip()}\n")
                    else:
                         results.append(f"Archivo: {f}: ✅ Sin errores detectados.\n")
                except Exception as e:
                     results.append(f"Error ejecutando eslint en {f}: {e}")
         else:
            results.append("⚠️ Advertencia: 'eslint' no encontrado. Instálalo con 'npm install -g eslint' para análisis de JS.")
    
    if not results:
        return "No se encontraron archivos soportados (Python/JS) para analizar o herramientas de linting instaladas."
        
    return "\n".join(results)


# Función alternativa para ejecución síncrona
def code_analysis_sync(analysis_type: str, path: str, recursive: bool = False) -> str:
    """
    Versión síncrona de code_analysis.
    Retorna el resultado completo como string.
    """
    output = []
    for chunk in code_analysis(analysis_type, path, recursive):
        output.append(chunk)
    return "".join(output)


# Schema de parámetros para el LLM
parameters_schema = {
    "type": "object",
    "properties": {
        "analysis_type": {
            "type": "string",
            "description": "Tipo de análisis: 'lint' (pylint/eslint), 'complexity' (ciclomática), 'maintainability' (índice MI), 'raw' (líneas, comentarios, etc.), 'halstead' (métricas Halstead)"
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