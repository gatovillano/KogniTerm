---
allowlist: false
author: KogniTerm AI (Autonomous Generation)
auto_approve: true
category: autonomous
dependencies: []
description: "Audita contenedores Docker y busca errores en logs seg\xFAn tiempo definido"
name: docker_audit
required_permissions:
- filesystem
sandbox_required: false
security_level: standard
tags:
- autonomous
- generated
version: 1.0.0
---

Audita contenedores Docker y genera reporte de errores.

## Uso
`/docker_audit` - Auditoría rápida (24h por defecto)
`/docker_audit time_range="1d"` - Auditoría de 1 día
`/docker_audit time_range="7d"` - Auditoría de 7 días

## Parámetros
- `time_range`: Rango de tiempo para búsqueda de errores (formato: "30m", "1h", "24h", "1d", "7d")

## Salida
JSON con estado de contenedores y errores detectados.