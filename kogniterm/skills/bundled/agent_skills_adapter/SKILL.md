---
name: agent_skills_adapter
version: 1.0.0
description: Guía procedimental para buscar e instalar skills desde skills.sh y GitHub usando únicamente la terminal, sin depender de la API REST ni de herramientas automatizadas.
category: system
security_level: standard
---

# Agent Skills Adapter (Procedural)

Esta skill no expone acciones ejecutables. Su propósito es instruir al agente sobre el flujo estándar para descubrir, evaluar e instalar skills externas sin usar tool calls automatizadas.

## Objetivo

Permitir que el agente extienda sus capacidades buscando e instalando skills de `skills.sh` o repositorios GitHub mediante comandos de terminal, manteniendo control total sobre cada paso.

## Flujo recomendado (paso a paso)

1. **Buscar skills relevantes**
   - Ejecuta en la terminal:
     - `npx skills find "<consulta>"` para buscar en `skills.sh`.
     - `npx skills list` para listar skills ya instaladas.
   - Si `npx skills` no está disponible, usa el buscador web manual:
     - `curl -s "https://skills.sh" | grep -i "<consulta>"` o abre `https://skills.sh` en el navegador.

2. **Inspeccionar la skill encontrada**
   - Revisa su `README` y `SKILL.md` para confirmar que se ajusta al caso de uso.
   - Verifica puntos clave:
     - Si es prompt-only: solo contiene instrucciones en `SKILL.md`.
     - Si es ejecutable: incluye `scripts/tool.py` con función `main` y `parameters_schema`.
     - Requisitos: dependencias, permisos, seguridad y alcance (workspace/global).

3. **Instalar la skill**
   - Desde `skills.sh`:
     - `npx skills install <skill_id>` (por ejemplo, `npx skills install vercel-labs/skills/find-skills`).
     - Si se requiere versión o skill concreta dentro de un repo, usa `npx skills install <repo_url> --skill <nombre>`.
   - Desde GitHub:
     - `git clone <repo_url>` o `gh repo clone <repo_url>` en la carpeta destino.
     - Copia la skill a:
       - Workspace: `<proyecto>/kogniterm/skills/workspace/<nombre>/`
       - Global: `~/.config/kogniterm/skills/<nombre>/`
   - Asegúrate de conservar la estructura estándar:
     - `SKILL.md`
     - `scripts/tool.py` (si aplica)
     - `references/` (opcional)
     - `assets/` (opcional)

4. **Registrar y refrescar**
   - Tras copiar la skill, refresca el sistema para que el `SkillManager` la detecte:
     - Reinicia KogniTerm, o
     - Usa el comando interno de recarga de skills si está disponible.
   - Verifica que aparece en la lista:
     - `npx skills list`
     - o el comando de KogniTerm que muestre skills cargadas.

5. **Validar funcionamiento**
   - Prompt-only: confirma que las instrucciones de `SKILL.md` son coherentes y no rompen el flujo del agente.
   - Ejecutable: prueba la skill con parámetros mínimos y valida salida.
   - Si hay errores, revisa rutas, imports y dependencias antes de reintentar.

## Notas operativas

- Prefiere `npx skills` antes que la API REST de `skills.sh`, que puede requerir autenticación adicional.
- Si una skill no encaja con el formato esperado, documenta las diferencias y evalúa si se puede adaptar manualmente.
- Para skills sensibles, respeta las políticas de seguridad del proyecto antes de instalarlas.
