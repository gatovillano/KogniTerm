---
name: refresh-tools
version: 1.0.0
author: "KogniTerm Core"
description: "Sincroniza y recarga el arsenal de herramientas. Úsalo después de crear una nueva skill para que aparezca en tu lista de comandos."
category: "meta"
tags: ["meta", "refresh", "sync"]
dependencies: []
required_permissions: ["logic"]
security_level: "low"
allowlist: true
auto_approve: true
sandbox_required: false
---

# Instrucciones para el LLM

Usa esta herramienta cuando hayas creado una nueva skill usando la `skill_factory` o hayas modificado archivos de herramientas directamente. Esto forzará al `ToolManager` a re-escanear los directorios y actualizar tu lista de herramientas disponibles.

## Cuándo usarla

- Inmediatamente después de llamar a `skill_factory`.
- Si sospechas que tu lista de herramientas está desactualizada.
