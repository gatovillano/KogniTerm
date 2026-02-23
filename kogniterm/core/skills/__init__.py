"""
Sistema de Skills para KogniTerm.

Este paquete implementa un sistema modular de skills con:
- Discovery automático en múltiples ubicaciones
- Carga dinámica (JIT) de módulos Python
- Validación de metadatos (SKILL.md)
- Migración automática de herramientas legacy
"""

from .skill_manager import SkillManager, Skill, SkillValidator, SkillLoader

__all__ = ['SkillManager', 'Skill', 'SkillValidator', 'SkillLoader']
