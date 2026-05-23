"""
SHIM DE COMPATIBILIDAD — kogniterm.terminal.security

Este módulo re-exporta todo desde kogniterm.ui.security para
mantener compatibilidad retroactiva con el código existente durante
la migración a la arquitectura cliente-servidor.

La implementación canónica ahora vive en: kogniterm/ui/security.py
"""

from kogniterm.ui.security import *  # noqa: F401, F403
from kogniterm.ui.security import scrub_secrets, mask_url_credentials  # exportaciones explícitas
