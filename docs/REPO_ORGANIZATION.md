# Propuesta de reorganización del repositorio

## 1) Resumen de la auditoría
- Código principal: `kogniterm/` (paquete Python) — mantener.
- Documentación extensa ya en `docs/` — centralizar ahí los .md sueltos.
- Tests en `tests/` — correcto.
- Varios scripts y parches en la raíz (`patch_llm_service.py`, `debug_tcss.py`, `planning_agent.py`, `run_tests.py`, etc.) — mover a `scripts/` o `tools/`.
- Artefactos generados: `kogniterm.egg-info/`, `dist/` — deben excluirse del repo o eliminarse y añadirse a `.gitignore`.

## 2) Propuesta de estructura (objetivo)

- `kogniterm/` — código fuente (mantener).
- `tests/` — tests unitarios e integración (mantener).
- `docs/` — documentación de usuario y arquitectura (centralizar aquí todos los .md de raíz).
- `scripts/` — utilidades y scripts de mantenimiento (mover: `patch_llm_service.py`, `debug_tcss*.py`, `planning_agent.py`, `run_tests.py`, `test_interrupt.sh`).
- `apps/` o mantener `kogniterm-desktop/` y `kogniterm-android/` — apps y frontends (mantener juntos si se prefiere `apps/`).
- `plans/` → `docs/plans/` (o integrarlo en `docs/plans/`).
- Eliminar/ignorar: `kogniterm.egg-info/`, `dist/`, `build/`.

## 3) Cambios seguros que apliqué ahora
- Actualicé `.gitignore` con entradas recomendadas (excluye `kogniterm.egg-info/`, caches y entornos virtuales).
- Añadí este documento `docs/REPO_ORGANIZATION.md` con la propuesta.

Archivos creados/modificados:
- `.gitignore` (actualizado)
- `docs/REPO_ORGANIZATION.md` (este archivo)

Pueden revisar los cambios en el repo antes de aplicar movimientos mayores.

## 4) Siguientes pasos propuestos (comandos sugeridos)

Ejemplos de comandos para aplicar la reorganización (ejecutar desde la raíz del repo):

```
mkdir -p scripts
git mv patch_llm_service.py scripts/
git mv debug_tcss.py debug_tcss_original.py scripts/
git mv planning_agent.py scripts/
git mv test_interrupt.sh scripts/
git mv plans docs/plans
git rm -r kogniterm.egg-info/  # borrar artefactos generados
git add .
git commit -m "Reorganiza: scripts/, docs/plans, limpia artefactos"
```

Nota: ejecutar los `git mv` uno a uno para revisar cada cambio.

## 5) Checklist de colaboración

- `README.md`: incluir sección “Estructura del proyecto” y link a `docs/REPO_ORGANIZATION.md`.
- `CONTRIBUTING.md`: pasos para desarrollo, estilo y pre-commit/formatters.
- Añadir CI: `.github/workflows/python-tests.yml` para ejecutar `pytest` en PRs.
- Verificar `pyproject.toml` vs `setup.py`: preferir `pyproject.toml` moderno si es viable.

---
Si quieres, aplico los `git mv` y los cambios propuestos (o lo hago por etapas).
