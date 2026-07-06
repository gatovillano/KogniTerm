from pathlib import Path
from typing import Optional, Dict, Any, List


def _external_skills_base() -> Path:
    return Path(__file__).resolve().parents[3] / "external"


def _iter_external_skills() -> List[Dict[str, Any]]:
    base = _external_skills_base()
    results: List[Dict[str, Any]] = []
    if not base.exists() or not base.is_dir():
        return results

    for skill_dir in sorted(base.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        results.append(
            {
                "name": skill_dir.name,
                "path": str(skill_dir),
                "description": "",
                "source": "external",
            }
        )
    return results


def list_available_external_skills() -> Dict[str, Any]:
    try:
        skills = _iter_external_skills()
        return {
            "success": True,
            "count": len(skills),
            "skills": skills,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def search_skills_catalog(query: str, limit: int = 10) -> Dict[str, Any]:
    try:
        query_lower = (query or "").strip().lower()
        skills = _iter_external_skills()
        if query_lower:
            skills = [
                s
                for s in skills
                if query_lower in s["name"].lower()
                or query_lower in s.get("description", "").lower()
            ]
        skills = skills[: max(1, limit)]
        return {
            "success": True,
            "count": len(skills),
            "results": skills,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def install_skill_pack_from_repo(repo_url: str, skill_name: Optional[str] = None) -> Dict[str, Any]:
    try:
        if not repo_url or not repo_url.strip():
            return {"success": False, "error": "repo_url vacío."}
        return {
            "success": False,
            "error": "Instalación desde repo no implementada en este adaptador.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
