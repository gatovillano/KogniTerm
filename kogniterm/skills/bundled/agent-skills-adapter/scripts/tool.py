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
    import tempfile
    import shutil
    import subprocess

    try:
        if not repo_url or not repo_url.strip():
            return {"success": False, "error": "repo_url vacío."}

        # Parse repo name
        name_part = repo_url.rstrip("/").split("/")[-1]
        if name_part.endswith(".git"):
            name_part = name_part[:-4]
        repo_name = name_part

        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone repo shallowly
            res = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, temp_dir],
                capture_output=True,
                text=True
            )
            if res.returncode != 0:
                return {
                    "success": False,
                    "error": f"Error clonando el repositorio: {res.stderr or res.stdout}"
                }

            # Find all directories with SKILL.md
            temp_path = Path(temp_dir)
            skill_dirs = []
            for skill_md in temp_path.rglob("SKILL.md"):
                skill_dirs.append(skill_md.parent)

            if not skill_dirs:
                return {
                    "success": False,
                    "error": "No se encontró ningún archivo SKILL.md en el repositorio."
                }

            dest_base = _external_skills_base()
            dest_base.mkdir(parents=True, exist_ok=True)
            installed_paths = []

            if skill_name:
                # Find specific skill matching skill_name
                matching_dir = None
                for sd in skill_dirs:
                    if sd.name.lower() == skill_name.lower():
                        matching_dir = sd
                        break
                if not matching_dir:
                    avail = ", ".join(d.name for d in skill_dirs)
                    return {
                        "success": False,
                        "error": f"La skill '{skill_name}' no existe en el repositorio. Disponibles: {avail}"
                    }
                # Copy it
                dest_dir = dest_base / matching_dir.name
                shutil.copytree(matching_dir, dest_dir, dirs_exist_ok=True)
                installed_paths.append(str(dest_dir))
            else:
                # Check if root contains SKILL.md (single skill repo)
                root_skill = temp_path / "SKILL.md"
                if root_skill.exists():
                    dest_dir = dest_base / repo_name
                    def ignore_git(dir_path, contents):
                        return ['.git'] if '.git' in contents else []
                    shutil.copytree(temp_dir, dest_dir, ignore=ignore_git, dirs_exist_ok=True)
                    installed_paths.append(str(dest_dir))
                else:
                    # Multiple skills repo - install all of them
                    for sd in skill_dirs:
                        dest_dir = dest_base / sd.name
                        shutil.copytree(sd, dest_dir, dirs_exist_ok=True)
                        installed_paths.append(str(dest_dir))

            return {
                "success": True,
                "message": "Skill(s) instalada(s) correctamente",
                "path": str(dest_base),
                "installed": installed_paths,
                "count": len(installed_paths)
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
