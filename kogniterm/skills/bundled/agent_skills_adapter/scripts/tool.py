#!/usr/bin/env python3
"""
Adaptador para skills de agent-skills y skills.sh en KogniTerm.

Soporta:
- Buscar skills en el catálogo de skills.sh
- Instalar skills individuales desde skills.sh
- Instalar packs completos desde repositorios GitHub
- Listar skills externas ya instaladas
- Cargar una skill por ruta local
- Ejecutar skills con función `main`
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
EXTERNAL_SKILLS_ROOT = PROJECT_ROOT / "kogniterm" / "skills" / "external"
SKILLS_SH_API = "https://skills.sh/api/v1"

# Mapa de esquemas de parámetros para las herramientas de este módulo
tool_schemas = {
    "main": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Acción a realizar: 'search', 'install', 'install_repo', 'load', 'execute', 'list'"
            },
            "query": {
                "type": "string",
                "description": "Consulta libre para buscar skills relevantes en skills.sh"
            },
            "skill_id": {
                "type": "string",
                "description": "ID estable de skills.sh (ej: 'vercel-labs/skills/find-skills')"
            },
            "install_url": {
                "type": "string",
                "description": "URL de instalación de skills.sh o GitHub (según fuente)"
            },
            "repo_url": {
                "type": "string",
                "description": "URL del repositorio GitHub que contiene una colección de skills"
            },
            "skill_name": {
                "type": "string",
                "description": "Nombre de una skill concreta dentro de un repo (opcional)"
            },
            "agent_skill_path": {
                "type": "string",
                "description": "Ruta local al directorio de la skill a cargar o ejecutar"
            },
            "parameters": {
                "type": "object",
                "description": "Parámetros para pasar a la skill cargada"
            },
            "limit": {
                "type": "integer",
                "description": "Cantidad máxima de resultados a devolver al buscar",
                "default": 10
            },
            "auto_install": {
                "type": "boolean",
                "description": "Si es true, instala automáticamente la mejor coincidencia de la búsqueda",
                "default": False
            }
        },
        "required": ["action"]
    },
    "load_agent_skill": {
        "type": "object",
        "properties": {
            "skill_path": {
                "type": "string",
                "description": "Ruta local al directorio de la skill a cargar"
            }
        },
        "required": ["skill_path"]
    },
    "execute_agent_skill": {
        "type": "object",
        "properties": {
            "skill_path": {
                "type": "string",
                "description": "Ruta local al directorio de la skill a ejecutar"
            },
            "parameters": {
                "type": "object",
                "description": "Parámetros para pasar a la función main de la skill"
            }
        },
        "required": ["skill_path", "parameters"]
    }
}


def main(**kwargs):
    """Función principal del adaptador de skills externas."""
    action = kwargs.get("action")
    query = kwargs.get("query")
    skill_id = kwargs.get("skill_id")
    install_url = kwargs.get("install_url")
    repo_url = kwargs.get("repo_url")
    skill_name = kwargs.get("skill_name")
    agent_skill_path = kwargs.get("agent_skill_path")
    parameters = kwargs.get("parameters", {}) or {}
    limit = int(kwargs.get("limit", 10) or 10)
    auto_install = bool(kwargs.get("auto_install", False))

    if action == "search":
        return search_skills_catalog(query=query or "", limit=limit)
    if action == "install":
        return install_skill_from_skills_sh(
            skill_id=skill_id,
            install_url=install_url,
            query=query,
            auto_install=auto_install,
        )
    if action == "install_repo":
        if not repo_url:
            return {"error": "Se requiere 'repo_url' para instalar un repo de skills"}
        return install_skill_pack_from_repo(repo_url=repo_url, skill_name=skill_name)
    if action == "list":
        return list_available_external_skills()
    if action == "load":
        if not agent_skill_path:
            return {"error": "Se requiere agent_skill_path para la acción 'load'"}
        return load_agent_skill(agent_skill_path)
    if action == "execute":
        if not agent_skill_path:
            return {"error": "Se requiere agent_skill_path para la acción 'execute'"}
        return execute_agent_skill(agent_skill_path, parameters)

    return {"error": f"Acción no soportada: {action}"}


def _safe_name(value: str) -> str:
    value = value.strip().replace(".git", "")
    value = re.sub(r"[^a-zA-Z0-9._/-]+", "-", value)
    value = value.strip("/-")
    return value or "skill"


def _external_dest_for_source(source: str) -> Path:
    safe = _safe_name(source)
    dest = EXTERNAL_SKILLS_ROOT / safe
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def _extract_skill_id(value: str) -> str:
    """Convierte una URL de skills.sh o un id en un id canónico."""
    value = value.strip()
    if "/api/v1/skills/" in value:
        value = value.split("/api/v1/skills/", 1)[1]
        value = value.split("?", 1)[0]
        return value.strip("/")
    if value.startswith("https://www.skills.sh/"):
        path = value.replace("https://www.skills.sh/", "", 1)
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3:
            return "/".join(parts[:3])
        if len(parts) == 2:
            return "/".join(parts)
    return value.strip("/")


def search_skills_catalog(query: str, limit: int = 10) -> Dict[str, Any]:
    """Busca skills relevantes en el catálogo de skills.sh."""
    if not query or len(query.strip()) < 2:
        return {"error": "La consulta debe tener al menos 2 caracteres"}

    try:
        response = requests.get(
            f"{SKILLS_SH_API}/skills/search",
            params={"q": query.strip(), "limit": max(1, min(limit, 200))},
            timeout=20,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("data", []) or []

        cleaned = []
        for item in results[:limit]:
            cleaned.append({
                "id": item.get("id"),
                "slug": item.get("slug"),
                "name": item.get("name"),
                "source": item.get("source"),
                "sourceType": item.get("sourceType"),
                "installs": item.get("installs", 0),
                "installUrl": item.get("installUrl"),
                "url": item.get("url"),
                "isDuplicate": item.get("isDuplicate", False),
            })

        return {
            "success": True,
            "query": query,
            "searchType": payload.get("searchType", "semantic"),
            "count": len(cleaned),
            "results": cleaned,
        }
    except Exception as exc:
        return {"error": f"Error buscando skills en skills.sh: {exc}"}


def install_skill_from_skills_sh(
    skill_id: Optional[str] = None,
    install_url: Optional[str] = None,
    query: Optional[str] = None,
    auto_install: bool = False,
) -> Dict[str, Any]:
    """Instala una skill individual desde skills.sh usando la API pública."""
    try:
        if not skill_id:
            if install_url:
                skill_id = _extract_skill_id(install_url)
            elif query:
                search_result = search_skills_catalog(query=query, limit=1)
                if "error" in search_result:
                    return search_result
                results = search_result.get("results", [])
                if not results:
                    return {"error": f"No se encontraron skills para '{query}'"}
                skill_id = results[0].get("id")
                install_url = results[0].get("installUrl")
                if not auto_install:
                    return {
                        "success": True,
                        "message": "Mejor coincidencia encontrada. Ejecuta nuevamente con auto_install=true para instalarla automáticamente.",
                        "best_match": results[0],
                        "candidates": results,
                    }
            else:
                return {"error": "Se requiere skill_id, install_url o query"}

        detail_response = requests.get(
            f"{SKILLS_SH_API}/skills/{quote(skill_id, safe='/')}",
            timeout=30,
            headers={"Accept": "application/json"},
        )
        detail_response.raise_for_status()
        detail = detail_response.json()

        files = detail.get("files")
        if not files:
            return {"error": f"No hay snapshot de archivos disponible para la skill '{skill_id}'"}

        dest_root = _external_dest_for_source(skill_id)
        dest_dir = dest_root / _safe_name(detail.get("slug") or skill_id.split("/")[-1])
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        for file_entry in files:
            rel_path = file_entry.get("path")
            contents = file_entry.get("contents", "")
            if not rel_path:
                continue
            target_path = dest_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(contents, encoding="utf-8")

        return {
            "success": True,
            "message": f"Skill '{skill_id}' instalada correctamente desde skills.sh",
            "path": str(dest_dir),
            "metadata": {
                "source": detail.get("source"),
                "slug": detail.get("slug"),
                "installs": detail.get("installs"),
                "hash": detail.get("hash"),
            },
        }
    except Exception as exc:
        return {"error": f"Error instalando skill desde skills.sh: {exc}"}


def install_skill_pack_from_repo(repo_url: str, skill_name: Optional[str] = None) -> Dict[str, Any]:
    """Clona un repo GitHub y copia una skill concreta o todas las skills detectadas."""
    repo_url = repo_url.strip()
    if not repo_url:
        return {"error": "repo_url vacío"}

    repo_slug = _safe_name(repo_url.split("github.com/", 1)[-1].replace(".git", ""))
    dest_root = _external_dest_for_source(repo_slug)

    try:
        with tempfile.TemporaryDirectory(prefix="kogniterm-skill-pack-") as tmpdir:
            clone_dir = Path(tmpdir) / "repo"
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(clone_dir)],
                check=True,
                capture_output=True,
                text=True,
            )

            if skill_name:
                candidates = [
                    clone_dir / skill_name,
                    clone_dir / "skills" / skill_name,
                ]
                source_dir = next((candidate for candidate in candidates if candidate.exists() and candidate.is_dir()), None)
                if not source_dir:
                    return {"error": f"No se encontró la skill '{skill_name}' en {repo_url}"}

                target_dir = dest_root / _safe_name(skill_name)
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(source_dir, target_dir)
                return {
                    "success": True,
                    "message": f"Skill '{skill_name}' instalada desde {repo_url}",
                    "path": str(target_dir),
                }

            installed = []
            for skill_file in clone_dir.rglob("SKILL.md"):
                skill_dir = skill_file.parent
                try:
                    relative_parts = skill_dir.relative_to(clone_dir).parts
                except ValueError:
                    relative_parts = skill_dir.parts
                if any(part.startswith(".") or part.startswith("_") for part in relative_parts):
                    continue
                if skill_dir.name in {"scripts", "references", "assets", "resources"}:
                    continue

                relative_dir = skill_dir.relative_to(clone_dir)
                target_dir = dest_root / relative_dir
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(skill_dir, target_dir)
                installed.append(str(target_dir))

            if not installed:
                return {"error": f"No se detectaron skills con SKILL.md en {repo_url}"}

            return {
                "success": True,
                "message": f"Repositorio instalado correctamente desde {repo_url}",
                "installed": installed,
                "count": len(installed),
                "path": str(dest_root),
            }
    except subprocess.CalledProcessError as exc:
        return {"error": f"Error clonando {repo_url}: {exc.stderr or exc.stdout or exc}"}
    except Exception as exc:
        return {"error": f"Error instalando pack de skills: {exc}"}


def list_available_external_skills() -> Dict[str, Any]:
    """Lista las skills externas ya instaladas en KogniTerm."""
    skills = []
    if EXTERNAL_SKILLS_ROOT.exists():
        for skill_file in EXTERNAL_SKILLS_ROOT.rglob("SKILL.md"):
            skill_dir = skill_file.parent
            try:
                content = skill_file.read_text(encoding="utf-8")
                metadata = {}
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        metadata = yaml.safe_load(parts[1]) or {}
                skills.append({
                    "name": metadata.get("name", skill_dir.name),
                    "description": metadata.get("description", ""),
                    "path": str(skill_dir),
                    "source": skill_dir.relative_to(EXTERNAL_SKILLS_ROOT).parts[0] if skill_dir.is_relative_to(EXTERNAL_SKILLS_ROOT) and skill_dir.relative_to(EXTERNAL_SKILLS_ROOT).parts else "external",
                })
            except Exception:
                skills.append({
                    "name": skill_dir.name,
                    "description": "",
                    "path": str(skill_dir),
                    "source": "external",
                })

    return {
        "success": True,
        "skills": skills,
        "count": len(skills),
        "message": "Listado de skills externas instaladas",
    }


def load_agent_skill(skill_path: str):
    """Carga una skill local de agent-skills o skills.sh y la prepara para su uso."""
    try:
        if not os.path.exists(skill_path):
            return {"error": f"La ruta de la skill no existe: {skill_path}"}

        skill_md_path = os.path.join(skill_path, "SKILL.md")
        if not os.path.exists(skill_md_path):
            return {"error": f"No se encontró SKILL.md en: {skill_path}"}

        with open(skill_md_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                yaml_content = parts[1]
                skill_metadata = yaml.safe_load(yaml_content) or {}
            else:
                skill_metadata = {}
        else:
            skill_metadata = {}

        scripts_dir = os.path.join(skill_path, "scripts")
        tool_py_path = os.path.join(scripts_dir, "tool.py")

        has_tool = False
        agent_skill_module = None

        if os.path.exists(tool_py_path):
            spec = importlib.util.spec_from_file_location("agent_skill", tool_py_path)
            if spec and spec.loader:
                agent_skill_module = importlib.util.module_from_spec(spec)
                sys.modules["agent_skill"] = agent_skill_module
                spec.loader.exec_module(agent_skill_module)

                if hasattr(agent_skill_module, 'main'):
                    has_tool = True
                else:
                    agent_skill_module = None

        return {
            "success": True,
            "skill_name": skill_metadata.get('name', 'unknown'),
            "version": skill_metadata.get('version', '1.0.0'),
            "description": skill_metadata.get('description', ''),
            "metadata": skill_metadata,
            "module": agent_skill_module,
            "has_tool": has_tool,
        }

    except Exception as e:
        return {"error": f"Error al cargar la skill: {str(e)}"}


def execute_agent_skill(skill_path: str, parameters: Dict[str, Any]):
    """Ejecuta una skill local con los parámetros dados."""
    try:
        load_result = load_agent_skill(skill_path)
        if "error" in load_result:
            return load_result

        if not load_result.get("has_tool", False):
            return {
                "success": True,
                "result": "Esta skill es una skill de instrucciones (Prompt-only) y no tiene una función ejecutable. Lee SKILL.md para usarla.",
                "skill_name": load_result["skill_name"],
            }

        agent_skill_module = load_result["module"]
        result = agent_skill_module.main(**parameters)

        return {
            "success": True,
            "result": result,
            "skill_name": load_result["skill_name"],
        }

    except Exception as e:
        return {"error": f"Error al ejecutar la skill: {str(e)}"}


if __name__ == "__main__":
    print(json.dumps(main(action="search", query="marketing", limit=3), indent=2, ensure_ascii=False))
