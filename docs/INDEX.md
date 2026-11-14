# Índice de documentación — KogniTerm

## Documentación canónica (vigente)
- [README.md](../README.md) — descripción general, instalación, arquitectura resumida y uso.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — guía de contribución.
- [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) — código de conducta.
- [PULL_REQUEST_TEMPLATE.md](../PULL_REQUEST_TEMPLATE.md) — plantilla de PR.
- [docs/](./) — documentación técnica y operativa (ver contenidos del directorio).
  - [docs/CLI_REFERENCE.md](./CLI_REFERENCE.md)
  - [docs/arquitectura_documentacion.md](./arquitectura_documentacion.md)
  - [docs/plan_migracion_cliente_servidor.md](./plan_migracion_cliente_servidor.md)
  - [docs/rag_implementation_plan.md](./rag_implementation_plan.md) y documentos relacionados
- [kogniterm/server/README.md](../kogniterm/server/README.md) — API/canales/sesiones del servidor.
- [pyproject.toml](../pyproject.toml) — metadatos, dependencias y scripts oficiales (`kogniterm`, `kogniterm-server`).

## Histórico / archivo
Documentos de análisis, auditorías, planes e investigaciones previas movidos desde la raíz para reducir ruido:
- [docs/archive/](./archive/)

> Nota: el contenido en `docs/archive/` se conserva por trazabilidad; puede estar desactualizado respecto al estado actual del código.

## Artefactos y utilidades
- [scripts/](../scripts/) — scripts de desarrollo/utilidad.
  - `scripts/concept_map_mcp_server.py` — servidor MCP independiente (mapas conceptuales/vis-network), no es el servidor principal de KogniTerm.
- `assets/` — recursos referenciados por documentación (p.ej. banner/demo en README).

## Notas de higiene (Fase 1)
- Artefactos grandes/binarios de raíz retirados del versionado en esta fase: `bandit_audit*.json`, `bandit_report.json`, `bandit_results.json`, `cleanup_report_dry.txt`, `test_wheel.zip`, `kogniterm*.cast` (raíz) y `kogniterm2.gif`, `kogniterm3.gif`. Permanecen en el historial de git (reducir tamaño del repo requiere reescritura de historial, paso separado).
- `kogniterm/archive_backups/*.bak` y backups similares dentro del paquete están versionados; evaluar su retiro en una fase posterior si no son necesarios para distribución/soporte.
- Otros artefactos/medios trackeados fuera de raíz (p.ej. `kogniterm/kogniterm5.gif`, backups en `kogniterm/archive_backups/`) siguen pendientes de decisión del mantenedor.
