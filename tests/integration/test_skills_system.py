#!/usr/bin/env python3
"""Test script to verify the skills system is working correctly"""

import sys
import os

# Add the project root to Python path
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from kogniterm.core.skills.skill_manager import SkillManager
from kogniterm.core.llm_service import LLMService


def test_skill_manager():
    """Test SkillManager initialization and skill discovery"""
    print("=== Testing SkillManager ===")
    
    try:
        skill_manager = SkillManager()
        print(f"✅ SkillManager initialized successfully")
        
        skills = skill_manager.discover_all_skills()
        print(f"✅ Discovered {len(skills)} skills")
        
        for skill in skills:
            print(f"  - {skill.name} (v{skill.version}) - {skill.description}")
            
            # Try to load the skill
            success = skill_manager.load_skill(skill.name)
            if success:
                print(f"    ✅ Loaded successfully")
            else:
                print(f"    ❌ Failed to load")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def test_llm_service_with_skills():
    """Test LLMService with SkillManager integration"""
    print("\n=== Testing LLMService with SkillManager ===")
    
    try:
        llm_service = LLMService(use_multi_provider=False)
        print(f"✅ LLMService initialized successfully")
        
        print(f"Total tools available: {len(llm_service.get_tools())}")
        
        print("\nTools registered in tool_map:")
        for tool_name, tool in llm_service.tool_map.items():
            print(f"  - {tool_name}")
            
        print("\nTools with skill information:")
        for tool_name, tool_info in llm_service.skill_manager.tool_registry.items():
            print(f"  - {tool_name} (Skill: {tool_info['skill']}, Security: {tool_info['security_level']})")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("Testing KogniTerm Skills System")
    print("=" * 50)
    
    test_skill_manager()
    test_llm_service_with_skills()
    
    print("\n" + "=" * 50)
    print("✅ Skills system test completed!")


if __name__ == "__main__":
    main()
