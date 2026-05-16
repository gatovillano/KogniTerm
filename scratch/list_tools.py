
import os
import sys
from pathlib import Path

# Añadir el directorio del proyecto al path
project_root = "/home/gato/Proyectos/Gemini-Interpreter"
sys.path.append(project_root)

from kogniterm.core.skills.skill_manager import SkillManager

def list_all_tools():
    sm = SkillManager()
    sm.discover_all_skills()
    
    # Cargar todas las skills para ver sus herramientas
    for skill_name in list(sm.skills.keys()):
        sm.load_skill(skill_name)
    
    print("--- REGISTERED TOOLS ---")
    for tool_name in sorted(sm.tool_registry.keys()):
        print(f"Tool: {tool_name}")
    print("------------------------")

if __name__ == "__main__":
    list_all_tools()
