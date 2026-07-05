# Design Spec: Git Skills Installer

This document outlines the design for installing external skills directly from a Git repository in KogniTerm.

## Context & Objectives
The user wants to run:
`kogniterm skills add https://github.com/obra/superpowers`
Currently, this fails because Git repository skill installation is not implemented in the adapter.

Our objective is to implement `install_skill_pack_from_repo` in `kogniterm/skills/bundled/agent-skills-adapter/scripts/tool.py` using Approach A (Subprocess git clone and directory copying).

## Detailed Design

### 1. Correcting Path Bug in `tool.py`
In `tool.py`, the helper `_external_skills_base()` incorrectly appends `skills` again:
`Path(__file__).resolve().parents[3] / "skills" / "external"`
Since `parents[3]` is already the `kogniterm/skills` directory, this resolves to `kogniterm/skills/skills/external`.
We will modify it to:
`Path(__file__).resolve().parents[3] / "external"`
This points correctly to `kogniterm/skills/external`.

### 2. Implementing `install_skill_pack_from_repo`
The function signature:
`def install_skill_pack_from_repo(repo_url: str, skill_name: Optional[str] = None) -> Dict[str, Any]`

**Execution Steps**:
1. Validate `repo_url`.
2. Extract the default repository name from the `repo_url` (e.g. `superpowers` for `https://github.com/obra/superpowers.git` or `https://github.com/obra/superpowers`).
3. Create a temporary directory using `tempfile.TemporaryDirectory()`.
4. Run `git clone --depth 1 {repo_url} {temp_dir}` using `subprocess.run` to fetch the repository quickly.
5. Search the temporary directory for directories containing `SKILL.md`.
6. Apply the installation logic:
   - **If `skill_name` is provided**:
     - Filter the found directories to find one whose directory name matches `skill_name` (case-insensitive).
     - If found:
       - Copy that subdirectory to `kogniterm/skills/external/{skill_name}`.
       - Return success with the installed path.
     - If not found:
       - Return error detailing that `skill_name` was not found in the repo, listing available skills in the repo.
   - **If `skill_name` is NOT provided**:
     - Check if the root of the cloned repo contains `SKILL.md`.
       - If it does, copy the root contents (excluding `.git`) to `kogniterm/skills/external/{repo_name}`.
     - If it does not, copy all subdirectories containing `SKILL.md` to `kogniterm/skills/external/{subdir_name}`.
     - Return success listing all installed skills.
7. Return a dictionary conforming to what KogniTerm CLI expects:
   ```python
   {
       "success": True,
       "message": "Skill(s) installed successfully.",
       "path": str(external_skills_base),
       "installed": list_of_installed_skills_paths,
       "count": len(list_of_installed_skills_paths)
   }
   ```

## Verification Plan
1. Fix the path bug and verify `kogniterm skills list` lists current external skills (like `find-skills` and `integrate-whatsapp`).
2. Run `kogniterm skills add https://github.com/obra/superpowers --skill brainstorming` and verify it installs `brainstorming` to `kogniterm/skills/external/brainstorming`.
3. Run `kogniterm skills list` to verify `brainstorming` is listed.
4. Run `kogniterm skills add https://github.com/obra/superpowers` and verify it installs the other skills.
