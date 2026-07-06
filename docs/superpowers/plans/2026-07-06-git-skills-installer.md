# Git Skills Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement skill installation from Git repositories in the KogniTerm CLI (`kogniterm skills add`).

**Architecture:** Use the system's `git clone --depth 1` command via python `subprocess` to clone repositories to a temporary directory, scan recursively for subdirectories containing `SKILL.md` (identifying skill locations), and copy them into the external skills directory (`kogniterm/skills/external/`).

**Tech Stack:** Python 3.12, Git, standard libraries (`subprocess`, `tempfile`, `shutil`, `pathlib`).

## Global Constraints
- Do not introduce external dependencies beyond the standard library or those already in `pyproject.toml` (e.g. GitPython is allowed, but native `subprocess` git commands are preferred for robustness).
- Ensure compatibility with environments where ECHO is disabled on the pseudo-terminal.

---

### Task 1: Fix External Skills Base Path Resolution in tool.py

Fix the `_external_skills_base()` path resolution logic in `kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py` so it points to `kogniterm/skills/external` instead of `kogniterm/skills/skills/external`.

**Files:**
- Modify: `kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py:5-7`
- Test: Run `venv/bin/kogniterm skills list`

**Interfaces:**
- Consumes: None
- Produces: `_external_skills_base() -> Path` (correctly pointing to `kogniterm/skills/external`)

- [ ] **Step 1: Write path correction in tool.py**

Replace `_external_skills_base` in [tool.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py):
```python
def _external_skills_base() -> Path:
    return Path(__file__).resolve().parents[3] / "external"
```

- [ ] **Step 2: Verify the path resolution**

Run: `venv/bin/kogniterm skills list`
Expected: Outputs `📦 Skills externas instaladas: 2` (since `find-skills` and `integrate-whatsapp` are in `kogniterm/skills/external/`).

- [ ] **Step 3: Commit path correction**

```bash
git add kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py
git commit -m "fix: correct _external_skills_base path resolution"
```

---

### Task 2: Implement Git Skills Installer in tool.py

Implement `install_skill_pack_from_repo(repo_url, skill_name)` in `kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py` to support cloning git repositories and installing skills.

**Files:**
- Modify: `kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py:65-72`
- Test: Run `venv/bin/kogniterm skills add https://github.com/obra/superpowers --skill brainstorming` and check folder.

**Interfaces:**
- Consumes: `_external_skills_base()`
- Produces: `install_skill_pack_from_repo(repo_url: str, skill_name: Optional[str] = None) -> Dict[str, Any]`

- [ ] **Step 1: Implement install_skill_pack_from_repo in tool.py**

Replace the placeholder function in [tool.py](file:///home/gato/Proyectos/Gemini-Interpreter/kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py) with the following:
```python
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
```

- [ ] **Step 2: Test installing a specific skill**

Run: `venv/bin/kogniterm skills add https://github.com/obra/superpowers --skill brainstorming`
Expected: `✅ Skill(s) instalada(s) correctamente` and checks output directory `kogniterm/skills/external/brainstorming`.

- [ ] **Step 3: Test listing installed skills**

Run: `venv/bin/kogniterm skills list`
Expected: `brainstorming` should be in the list.

- [ ] **Step 4: Commit Git skills installer implementation**

```bash
git add kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py
git commit -m "feat: implement Git skills installation from repo url"
```
