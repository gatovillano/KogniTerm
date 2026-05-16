
import os
import sys
from pathlib import Path
import asyncio

# Añadir el directorio del proyecto al path
project_root = "/home/gato/Proyectos/KognitoAI/kognito-ai"
sys.path.append(project_root)

# Mock some dependencies if needed or just try to import
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db" # dummy
os.environ["OPENAI_API_KEY"] = "sk-..." # dummy

from core.skill_manager import get_skill_manager

async def list_all_tools():
    sm = get_skill_manager()
    # We need to simulate a call to load_skills
    # But first, let's just see what's in the folders
    
    print("--- SKILLS DIRECTORY ---")
    skills_dir = sm.skills_dir
    print(f"Skills Dir: {skills_dir}")
    
    tools = await sm.load_skills(account_id="5b8d59b0-69b7-4aa8-9bb0-bf07511222a6")
    
    print("--- REGISTERED TOOLS IN KOGNITOAI ---")
    for tool in sorted(tools, key=lambda t: t.name):
        print(f"Tool: {tool.name}")
    print("-------------------------------------")

if __name__ == "__main__":
    asyncio.run(list_all_tools())
