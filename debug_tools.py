import os
import sys
import json
from pathlib import Path

# Añadir el directorio actual al path para poder importar kogniterm
sys.path.append(os.getcwd())

from kogniterm.core.skills.skill_manager import SkillManager

def show_schema():
    sm = SkillManager()
    sm.discover_all_skills()
    sm.load_skill("file_operations")
    
    tool_info = sm.tool_registry.get("sophisticated_editor_tool")
    if tool_info:
        tool = tool_info['tool']
        # SkillManager.get_tools_for_llm uses the schema
        tools_for_llm = sm.get_tools_for_llm()
        for t in tools_for_llm:
            if t['name'] == "sophisticated_editor_tool":
                print(json.dumps(t, indent=2))
    else:
        print("Herramienta sophisticated_editor_tool no encontrada.")

if __name__ == "__main__":
    show_schema()
