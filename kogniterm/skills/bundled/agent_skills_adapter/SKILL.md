---
name: agent_skills_adapter
version: 1.0.0
description: Adaptador para permitir que skills diseñadas para el framework agent-skills funcionen en KogniTerm
category: system
security_level: standard
---

# Agent Skills Adapter

Este adaptador permite que KogniTerm utilice skills que fueron diseñadas siguiendo la especificación del framework agent-skills.

## Funcionalidad

1. Detecta skills en formato agent-skills
2. Las convierte a un formato compatible con KogniTerm
3. Las registra en el sistema de skills de KogniTerm
4. Busca skills nuevas en skills.sh mediante su API pública
5. Instala skills individuales desde skills.sh usando su `SKILL.md` y archivos asociados
6. Instala packs completos de skills desde repositorios GitHub
7. Proporciona una interfaz uniforme para invocar tanto skills nativas de KogniTerm como skills externas instaladas

## Uso

Una vez instalado, el adaptador se ejecuta automáticamente y hace disponibles las skills de agent-skills como si fueran skills nativas de KogniTerm.

Acciones soportadas:
- `search`: buscar skills en skills.sh
- `install`: instalar una skill concreta desde skills.sh
- `install_repo`: clonar e instalar un pack de skills desde GitHub
- `list`: listar skills externas ya instaladas
- `load`: cargar una skill local
- `execute`: ejecutar una skill local que tenga función `main`

## Compatibilidad

Este adaptador es compatible con skills que siguen la especificación básica de agent-skills, que incluye:
- YAML frontmatter con nombre, versión, descripción
- Implementación en Python con una función principal
- Esquema de parámetros definido