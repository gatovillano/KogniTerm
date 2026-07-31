# Reglas de Desarrollo para KogniTerm

## Pseudo-terminales y Entornos Sin Eco
Al modificar el motor de ejecución de comandos (`CommandExecutor`) o cualquier lógica relacionada con el procesamiento y parseo de entradas/salidas de terminal, se debe garantizar la compatibilidad con terminales donde `ECHO` está desactivado (ej. ejecución en segundo plano, daemons o modo servidor).

- **Filtrado de Eco**: No asumas que la terminal siempre repetirá (echo) el comando enviado. El filtro de eco debe diferenciar explícitamente entre la línea de eco del comando y el marcador de finalización limpio (`##KOGNITERM_DONE_MARKER##`).
- **Bloqueos**: Si se descarta erróneamente el marcador de finalización confundiéndolo con un eco de comando, la ejecución del comando se quedará bloqueada en espera de más salida. Siempre verifica de forma estricta que la línea a descartar no sea idéntica al marcador limpio.

## Formato Estándar para Skills (`SKILL.md`)
Al crear o modificar cualquier **Skill** (usando `writing-skills`, `workflow-skill-creator` o manualmente), se debe seguir estrictamente la especificación oficial de **[Agent Skills Specification](https://agentskills.io/specification)**:

1. **Estructura de Directorios**:
   - Cada skill es un directorio cuyo nombre coincide exactamente con el campo `name` de `SKILL.md`.
   - Contiene un archivo obligatorio `SKILL.md` y subdirectorios opcionales: `scripts/`, `references/`, `assets/`, `resources/`.

2. **Encabezado / Frontmatter (YAML obligatorio)**:
   ```yaml
   ---
   name: nombre-del-skill
   description: Use when [qué hace el skill y condiciones exactas de activación]
   metadata:
     version: "1.0.0"
     author: "Nombre / Org"
   ---
   ```
   - **`name`**: 1-64 caracteres. Solo letras minúsculas (`a-z`), números (`0-9`) y guiones (`-`). No puede empezar/terminar con guión ni tener guiones consecutivos (`--`). Debe coincidir con el nombre de la carpeta padre.
   - **`description`**: 1-1024 caracteres. Debe comenzar siempre con `"Use when..."` en tercera persona. Describe qué hace la habilidad y cuándo debe activarse (disparadores, síntomas y palabras clave). **NUNCA** resumas el flujo ni el procedimiento interno para evitar que los agentes se salten el cuerpo del skill.

3. **Cuerpo del Documento (`SKILL.md`)**:
   - Markdown estructurado (recomendado bajo 500 líneas para revelación progresiva).
   - Secciones recomendadas: `# Nombre`, `## Overview`, `## When to Use`, `## Core Pattern / Instrucciones`, `## Quick Reference / Ejemplos`, `## Common Mistakes / Red Flags`.
   - Documentación y referencias extensas (>100 líneas) deben moverse a archivos dentro de `references/`.


