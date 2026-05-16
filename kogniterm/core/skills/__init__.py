"""
Sistema de Skills para KogniTerm.

Este paquete implementa un sistema modular de skills con:
- Discovery automático en múltiples ubicaciones
- Compatibilidad con manifiestos `SKILL.md` estilo Agent Skills / Skills SH
- Carga dinámica (JIT) de módulos Python cuando existen scripts ejecutables
- Skills prompt-only y skills con herramientas convivientes
- Migración automática de herramientas legacy
"""

from .skill_manager import SkillManager, Skill, SkillValidator, SkillLoader

__all__ = ['SkillManager', 'Skill', 'SkillValidator', 'SkillLoader']
