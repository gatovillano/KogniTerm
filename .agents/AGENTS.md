# Reglas de Desarrollo para KogniTerm

## Pseudo-terminales y Entornos Sin Eco
Al modificar el motor de ejecución de comandos (`CommandExecutor`) o cualquier lógica relacionada con el procesamiento y parseo de entradas/salidas de terminal, se debe garantizar la compatibilidad con terminales donde `ECHO` está desactivado (ej. ejecución en segundo plano, daemons o modo servidor).

- **Filtrado de Eco**: No asumas que la terminal siempre repetirá (echo) el comando enviado. El filtro de eco debe diferenciar explícitamente entre la línea de eco del comando y el marcador de finalización limpio (`##KOGNITERM_DONE_MARKER##`).
- **Bloqueos**: Si se descarta erróneamente el marcador de finalización confundiéndolo con un eco de comando, la ejecución del comando se quedará bloqueada en espera de más salida. Siempre verifica de forma estricta que la línea a descartar no sea idéntica al marcador limpio.

## Formato Estándar para Skills (`SKILL.md`)
Al crear o modificar cualquier **Skill** (usando `writing-skills`, `workflow-skill-creator` o manualmente), se debe seguir estrictamente la siguiente especificación de formato:

1. **Encabezado / Frontmatter (YAML obligatorio)**:
   ```yaml
   ---
   name: nombre-del-skill-con-guiones
   description: Use when [condiciones exactas de activación y síntomas del problema]
   ---
   ```
   - **`name`**: Nombre descriptivo en minúsculas separado por guiones (letras, números y guiones únicamente).
   - **`description`**: Debe comenzar siempre con `"Use when..."` en tercera persona. Describe únicamente las **condiciones de disparo** y los síntomas/contextos del problema. **NUNCA** resumas el flujo ni el proceso interno del skill en la descripción para evitar que los agentes tomen atajos sin leer el cuerpo completo. Longitud máxima recomendada: 500 caracteres (máx. 1024 caracteres en todo el frontmatter).

2. **Estructura del Cuerpo (`SKILL.md`)**:
   - `# Nombre del Skill`
   - `## Overview`: Principio fundamental o propósito en 1-2 oraciones.
   - `## When to Use`: Lista de síntomas, condiciones de activación y cuándo NO usarlo.
   - `## Core Pattern / Instrucciones`: Explicación clara del patrón, flujo o método paso a paso (ejemplo antes/después si aplica).
   - `## Quick Reference / Ejemplos`: Comandos, tablas o fragmentos de código reutilizables y listos para ejecutar.
   - `## Common Mistakes / Red Flags`: Errores comunes, racionalizaciones prohibidas y cómo evitarlos.

3. **Organización y Límites de Archivos**:
   - Mantener el archivo `SKILL.md` por debajo de **500 líneas**.
   - Para referencias o documentación de más de 100 líneas, mover el contenido a archivos dedicados en un subdirectorio `references/`.
   - Utilizar subdirectorios opcionales para recursos adicionales: `scripts/` (herramientas/scripts ejecutables), `examples/` (ejemplos extensos) y `resources/` (plantillas o activos).

