"""Tests unitarios para SkillManager"""

import pytest
from kogniterm.core.skills.skill_manager import SkillManager


@pytest.fixture
def skill_manager():
    """Instancia de SkillManager para tests"""
    return SkillManager()


def test_skill_manager_initialization(skill_manager):
    """Prueba que SkillManager se inicializa correctamente"""
    assert skill_manager is not None
    assert hasattr(skill_manager, 'skill_registry')
    assert hasattr(skill_manager, 'load_skill')


def test_discover_all_skills(skill_manager):
    """Prueba que discover_all_skills encuentra habilidades"""
    skills = skill_manager.discover_all_skills()
    assert isinstance(skills, list)
    assert len(skills) > 0  # Debería encontrar al menos algunas skills


def test_skill_registry_structure(skill_manager):
    """Prueba la estructura del registro de habilidades"""
    skill_manager.discover_all_skills()
    
    for skill_name, skill_info in skill_manager.skill_registry.items():
        assert 'skill' in skill_info
        assert 'security_level' in skill_info
        assert 'description' in skill_info
        assert 'version' in skill_info
        assert isinstance(skill_info['security_level'], str)


def test_load_skill_by_name(skill_manager):
    """Prueba la carga de una skill específica"""
    # Obtener nombres disponibles
    skill_manager.discover_all_skills()
    available_skills = list(skill_manager.skill_registry.keys())
    
    if not available_skills:
        pytest.skip("No hay skills disponibles para probar")
    
    skill_name = available_skills[0]
    result = skill_manager.load_skill(skill_name)
    
    assert result is not None, f"No se pudo cargar la skill {skill_name}"


def test_get_tools(skill_manager):
    """Prueba que get_tools retorna herramientas válidas"""
    skill_manager.discover_all_skills()
    tools = skill_manager.get_tools()
    
    assert isinstance(tools, list)
    
    for tool in tools:
        assert hasattr(tool, 'name')
        assert hasattr(tool, 'description')
        assert hasattr(tool, 'args_schema')
