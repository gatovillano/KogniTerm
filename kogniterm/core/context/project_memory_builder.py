from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Any
import os
import tomllib


class ProjectMemoryBuilder:
    """Genera una memoria de alto nivel del proyecto para %init."""

    DEFAULT_MEMORY_FILE = "llm_context.md"

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)

    def build_markdown(self, llm_service: Optional[Any] = None) -> str:
        # 1. Si hay un servicio LLM disponible, intentar realizar investigación automática
        if llm_service:
            ai_memory = self.investigate_with_llm(llm_service)
            if ai_memory:
                return ai_memory

        # 2. Si hay instrucciones existentes de copilot/etc, usarlas
        existing_instructions = self._read_text(
            self.root_dir / ".github" / "copilot-instructions.md",
            max_chars=50000,
        )
        if existing_instructions.strip():
            return self._normalize_existing_instructions(existing_instructions)
            
        # 3. Fallback a la generación heurística estructurada
        return self._build_fallback_markdown()

    def write_memory_file(
        self, content: str, file_path: str = DEFAULT_MEMORY_FILE
    ) -> Path:
        kogniterm_dir = self.root_dir / ".kogniterm"
        kogniterm_dir.mkdir(parents=True, exist_ok=True)
        full_path = kogniterm_dir / Path(file_path).name
        full_path.write_text(content.strip() + "\n", encoding="utf-8")
        return full_path

    def investigate_with_llm(self, llm_service: Any) -> Optional[str]:
        """Realiza una investigación local utilizando el LLM y DeepResearcher."""
        try:
            # 1. Asegurar que las herramientas críticas estén cargadas en el LLMService
            if hasattr(llm_service, 'skill_manager'):
                for skill in ['file_operations', 'codebase_search', 'task_tracker']:
                    try:
                        if skill not in llm_service.skill_manager.loaded_skills:
                            llm_service.skill_manager.load_skill(skill)
                    except Exception:
                        pass
            
            # 2. Obtener el terminal_ui e interrupt_queue del servicio o manager
            terminal_ui = getattr(llm_service, 'terminal_ui', None)
            if not terminal_ui and hasattr(llm_service, 'skill_manager'):
                terminal_ui = getattr(llm_service.skill_manager, 'terminal_ui', None)
                
            interrupt_queue = getattr(llm_service, 'interrupt_queue', None)
            if not interrupt_queue and hasattr(llm_service, 'skill_manager'):
                interrupt_queue = getattr(llm_service.skill_manager, 'interrupt_queue', None)

            # 3. Crear DeepResearcher
            from kogniterm.core.agents.deep_researcher import create_deep_researcher
            app = create_deep_researcher(
                llm_service=llm_service,
                terminal_ui=terminal_ui,
                interrupt_queue=interrupt_queue
            )
            
            query = (
                "Realiza una investigación profunda y exhaustiva del proyecto local para generar su Memoria Contextual. "
                "Revisa la estructura de directorios, los archivos de configuración (como pyproject.toml, package.json, etc.), "
                "los módulos del core en el código fuente, los archivos de test y el README.md. "
                "Debes recopilar suficiente información para estructurar el informe final (llm_context.md) con las siguientes secciones exactas:\n"
                "1. # Memoria Contextual del Proyecto: propósito principal, tecnologías clave y alcance del proyecto.\n"
                "2. ## Arquitectura y Módulos Clave: explicación de la estructura de carpetas, responsabilidades de los módulos y flujo de ejecución.\n"
                "3. ## Comandos del Proyecto: comandos útiles de bash/npm/pytest para instalación, ejecución y pruebas.\n"
                "4. ## Convenciones y Reglas de Desarrollo: estilo de código, patrones de diseño, decisiones y reglas obligatorias."
            )
            
            from langchain_core.messages import HumanMessage
            from kogniterm.core.agents.deep_researcher import DeepResearchState
            
            # Inicializar el estado de Deep Research
            initial_state = DeepResearchState()
            initial_state.messages = [HumanMessage(content=query)]
            
            # Ejecutar el grafo
            final_state = app.invoke(initial_state)
            
            # El último mensaje en final_state.messages es el reporte de síntesis generado
            if final_state and 'messages' in final_state and final_state['messages']:
                last_msg = final_state['messages'][-1]
                content = getattr(last_msg, 'content', '')
                if content:
                    # Limpiar marcadores de pensamiento/razonamiento
                    import re
                    cleaned_content = content.strip()
                    cleaned_content = re.sub(r'<thought>.*?</thought>', '', cleaned_content, flags=re.DOTALL | re.IGNORECASE)
                    cleaned_content = re.sub(r'<thinking>.*?</thinking>', '', cleaned_content, flags=re.DOTALL | re.IGNORECASE)
                    cleaned_content = cleaned_content.replace('__THINKING__:', '')
                    cleaned_content = cleaned_content.replace('__THINKING__', '')
                    cleaned_content = cleaned_content.strip()
                    
                    if cleaned_content:
                        # Si tiene el encabezado de Síntesis del DeepResearcher, limpiarlo para dejar un markdown limpio
                        if cleaned_content.startswith("## 🔬 Informe de Deep Research"):
                            cleaned_content = cleaned_content.replace("## 🔬 Informe de Deep Research\n\n", "")
                        elif cleaned_content.startswith("## 🔬 Informe de Investigación"):
                            cleaned_content = cleaned_content.replace("## 🔬 Informe de Investigación\n\n", "")
                            
                        header = "<!-- Generado por KogniTerm DeepResearcher -->\n"
                        if cleaned_content.startswith("# Memoria Contextual") or cleaned_content.startswith("<!--"):
                            return cleaned_content
                        return header + cleaned_content
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error running DeepResearcher in ProjectMemoryBuilder: {e}", exc_info=True)
            
        return None

    def _normalize_existing_instructions(self, content: str) -> str:
        lines = content.strip().splitlines()
        if lines and lines[0].lstrip().startswith("# "):
            lines = lines[1:]

        body = "\n".join(lines).strip()
        if not body:
            return self._build_fallback_markdown()

        return "# Memoria Contextual del Proyecto\n\n" + body

    def _build_fallback_markdown(self) -> str:
        commands = self._build_commands_section()
        architecture = self._build_architecture_section()
        conventions = self._build_conventions_section()

        sections = [
            "# Memoria Contextual del Proyecto",
            "",
            "## Build, test, and lint commands",
            "",
            *commands,
            "",
            "## High-level architecture",
            "",
            *architecture,
            "",
            "## Key conventions",
            "",
            *conventions,
        ]
        return "\n".join(sections).strip()

    def _build_commands_section(self) -> List[str]:
        lines: List[str] = ["```bash"]

        if (self.root_dir / "pyproject.toml").exists() or (self.root_dir / "setup.py").exists():
            lines.append("python -m pip install -e .")

        if (self.root_dir / "kogniterm" / "terminal" / "terminal.py").exists():
            lines.append("python -m kogniterm.terminal.terminal")
            lines.append("kogniterm")
            lines.append("kogniterm --cli")

        if (self.root_dir / "tests").exists():
            lines.append("python -m pytest tests/")
            if (self.root_dir / "run_tests.py").exists():
                lines.append("python run_tests.py")
                lines.append(
                    'python -c "import run_tests; run_tests.run_unit_tests()"'
                )
                lines.append(
                    'python -c "import run_tests; run_tests.run_integration_tests()"'
                )

            single_test = self._pick_single_test_target()
            if single_test:
                lines.append(f"python -m pytest {single_test}")
                if single_test == "tests/test_basic.py":
                    lines.append(
                        "python -m pytest tests/test_basic.py::test_logger_setup"
                    )

        # Buscar comandos genéricos npm/yarn si es node
        if (self.root_dir / "package.json").exists():
            lines.append("npm install")
            lines.append("npm start")
            lines.append("npm test")

        lint_note = self._infer_lint_note()
        if lint_note:
            lines.append(lint_note)

        lines.append("```")
        return lines

    def _pick_single_test_target(self) -> Optional[str]:
        preferred = self.root_dir / "tests" / "test_basic.py"
        if preferred.exists():
            return "tests/test_basic.py"

        for path in sorted((self.root_dir / "tests").rglob("test_*.py")):
            rel = path.relative_to(self.root_dir).as_posix()
            if "__pycache__" not in rel:
                return rel
        return None

    def _infer_lint_note(self) -> Optional[str]:
        contributing = self._read_text(self.root_dir / "CONTRIBUTING.md", max_chars=12000)
        mentions_black = "`black`" in contributing or "black " in contributing
        mentions_isort = "`isort`" in contributing or "isort " in contributing
        if mentions_black and mentions_isort:
            return "# no lint task is wired in CI; CONTRIBUTING.md recommends black . && isort ."
        return None

    def _build_architecture_section(self) -> List[str]:
        bullets: List[str] = []

        # 1. Casos específicos de KogniTerm para conservar la lógica del repo original
        if (self.root_dir / "kogniterm" / "terminal" / "terminal.py").exists():
            bullets.append(
                "- `kogniterm/terminal/terminal.py`: Punto de entrada real de KogniTerm. Elige entre CLI en `terminal/cli.py` y la TUI."
            )

        if (self.root_dir / "kogniterm" / "core" / "llm_service.py").exists():
            bullets.append(
                "- `kogniterm/core/llm_service.py`: Cerebro del sistema (modelos, proveedores, RAG y gestión de historial)."
            )

        if all(
            (self.root_dir / "kogniterm" / "core" / part).exists()
            for part in ("agent_state.py", "message_manager.py", "history_manager.py")
        ):
            bullets.append(
                "- `kogniterm/core/`: División de responsabilidades entre `AgentState` (flags), `MessageManager` (mensajes) y `HistoryManager` (persistencia)."
            )

        # 2. Análisis genérico de directorios para cualquier proyecto
        main_dirs = ["src", "app", "lib", "core", "api", "components", "frontend", "backend", "tests"]
        found_dirs = []
        for d in main_dirs:
            if (self.root_dir / d).exists() and (self.root_dir / d).is_dir():
                found_dirs.append(d)

        if found_dirs:
            bullets.append(f"- Estructura modular detectada: {', '.join([f'`{d}/`' for d in found_dirs])}.")
            for d in found_dirs:
                try:
                    subdirs = [sub.name for sub in (self.root_dir / d).iterdir() if sub.is_dir() and not sub.name.startswith('.')][:4]
                    if subdirs:
                        bullets.append(f"  - `{d}/` contiene componentes como: {', '.join([f'`{sd}`' for sd in subdirs])}.")
                except Exception:
                    pass

        # 3. Intentar extraer descripción breve de README.md
        readme = self._read_text(self.root_dir / "README.md", max_chars=4000)
        if readme:
            lines = [l.strip() for l in readme.splitlines() if l.strip()]
            desc_lines = []
            for i, line in enumerate(lines):
                if line.startswith("# ") and i + 1 < len(lines):
                    idx = i + 1
                    while idx < len(lines) and not lines[idx].startswith("#") and len(desc_lines) < 2:
                        desc_lines.append(lines[idx])
                        idx += 1
                    break
            if desc_lines:
                bullets.insert(0, f"- **Propósito del Proyecto:** {' '.join(desc_lines)}")

        if not bullets:
            bullets.append("- Revisa la documentación general del repositorio; no se identificaron módulos estándar.")

        return bullets

    def _build_conventions_section(self) -> List[str]:
        bullets: List[str] = []
        
        main_py = self._read_text(self.root_dir / "kogniterm" / "main.py", max_chars=1000)
        if "ya no es el punto de entrada principal" in main_py:
            bullets.append(
                "- No rutes nuevo comportamiento de inicio por `kogniterm/main.py` (obsoleto)."
            )

        # 1. Detectar tipo de lenguaje/proyecto
        if (self.root_dir / "package.json").exists():
            bullets.append("- Proyecto Node.js/JavaScript: sigue las convenciones de npm/yarn/pnpm y estilos ESLint/Prettier.")
        if (self.root_dir / "pyproject.toml").exists() or (self.root_dir / "requirements.txt").exists():
            bullets.append("- Proyecto Python: sigue las convenciones PEP 8 y entornos virtuales aislados.")
        if (self.root_dir / "Cargo.toml").exists():
            bullets.append("- Proyecto Rust: estructurado alrededor de Cargo.")

        # 2. Idioma predominante
        readme = self._read_text(self.root_dir / "README.md", max_chars=10000)
        if any(token in readme for token in (" es ", " tu ", " asistente ", "proyecto", "código")):
            bullets.append("- Se prefiere escribir comentarios, commits y documentación en español.")
        else:
            bullets.append("- Comments, commits and documentation are written primarily in English.")

        # 3. Estado local
        if (self.root_dir / ".kogniterm").exists() or (self.root_dir / "kogniterm").exists():
            bullets.append("- El estado local y la base vectorial residen bajo la carpeta `.kogniterm/` del espacio de trabajo.")

        return bullets

    def _read_text(self, path: Path, max_chars: int) -> str:
        if not path.exists() or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        except OSError:
            return ""

    def _load_pyproject(self) -> dict:
        pyproject_path = self.root_dir / "pyproject.toml"
        if not pyproject_path.exists():
            return {}
        try:
            with pyproject_path.open("rb") as f:
                return tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            return {}
