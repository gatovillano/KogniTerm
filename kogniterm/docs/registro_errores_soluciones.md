# Registro de Errores y Soluciones KogniTerm

## 26-01-2026 SyntaxError en ResearchAgents

**Descripción del Error:**
Al iniciar la aplicación, se producían múltiples `SyntaxError` en `kogniterm/core/agents/research_agents.py`.

1. `SyntaxError: invalid character '¿'`: Causado por un docstring mal formado (triple comilla faltante) que dejaba texto fuera de la cadena.
2. `SyntaxError: invalid syntax`: Causado por el uso incorrecto de `BACKSTORY:` como etiqueta en lugar de asignar la variable `backstory`.
3. Errores de comas sobrantes en cadenas de texto.

**Solución Aplicada:**

- Se corrigió la asignación de `backstory` en los agentes `codebase_specialist` y otros, asegurando el formato `backstory="""..."""`.
- Se eliminaron las comillas triples mal colocadas y comas redundantes.
- Se verificó la sintaxis exitosamente con `python -m py_compile`.
