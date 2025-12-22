import os
import logging
from typing import Type, Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

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

class CodeAnalysisTool(BaseTool):
    name: str = "code_analysis"
    description: str = "Realiza análisis estático de código Python utilizando la librería 'radon'. Permite calcular Complejidad Ciclomática, Índice de Mantenibilidad y métricas 'raw'."

    llm_service: Any
    
    def __init__(self, llm_service: Any, **kwargs):
        super().__init__(llm_service=llm_service, **kwargs)
        self.llm_service = llm_service

    class CodeAnalysisInput(BaseModel):
        analysis_type: str = Field(..., description="Tipo de análisis: 'complexity' (ciclomática), 'maintainability' (índice MI), 'raw' (líneas, comentarios, etc.), 'halstead' (métricas Halstead).")
        path: str = Field(..., description="Ruta al archivo o directorio a analizar.")
        recursive: bool = Field(default=False, description="Si es True y path es un directorio, busca archivos recursivamente.")

    args_schema: Type[BaseModel] = CodeAnalysisInput

    def _run(self, analysis_type: str, path: str, recursive: bool = False) -> Union[str, Dict[str, Any]]:
        if radon_cc is None:
            return "Error: La librería 'radon' no está instalada. Por favor instálala con `pip install radon`."

        path = path.strip().replace('@', '')
        if not os.path.exists(path):
            return f"Error: La ruta '{path}' no existe."

        try:
            if analysis_type == 'complexity':
                return self._analyze_complexity(path, recursive)
            elif analysis_type == 'maintainability':
                return self._analyze_maintainability(path, recursive)
            elif analysis_type == 'raw':
                return self._analyze_raw(path, recursive)
            elif analysis_type == 'halstead':
                return self._analyze_halstead(path, recursive)
            else:
                return f"Error: Tipo de análisis '{analysis_type}' no soportado."
        except Exception as e:
            logger.error(f"Error en análisis de código: {e}")
            return f"Error durante el análisis: {str(e)}"

    def _get_files(self, path: str, recursive: bool) -> List[str]:
        files_to_analyze = []
        if os.path.isfile(path):
            if path.endswith('.py'):
                files_to_analyze.append(path)
        elif os.path.isdir(path):
            if recursive:
                for root, _, files in os.walk(path):
                    for file in files:
                        if file.endswith('.py'):
                            files_to_analyze.append(os.path.join(root, file))
            else:
                for file in os.listdir(path):
                    full_path = os.path.join(path, file)
                    if os.path.isfile(full_path) and file.endswith('.py'):
                        files_to_analyze.append(full_path)
        return files_to_analyze

    def _analyze_complexity(self, path: str, recursive: bool) -> str:
        files = self._get_files(path, recursive)
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

    def _analyze_maintainability(self, path: str, recursive: bool) -> str:
        files = self._get_files(path, recursive)
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

    def _analyze_raw(self, path: str, recursive: bool) -> str:
        files = self._get_files(path, recursive)
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

    def _analyze_halstead(self, path: str, recursive: bool) -> str:
        files = self._get_files(path, recursive)
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