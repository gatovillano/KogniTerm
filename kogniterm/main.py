"""Compatibilidad de punto de entrada.

Este módulo no contiene la lógica principal de arranque. Los entrypoints
oficiales del proyecto son:
- CLI/TUI: `kogniterm.terminal.terminal:main` (script `kogniterm`)
- Servidor: `kogniterm.server.__main__:main` (script `kogniterm-server`)

Ver `pyproject.toml` ([project.scripts]) como fuente canónica.
"""

from kogniterm.terminal.terminal import main


if __name__ == "__main__":
    main()
