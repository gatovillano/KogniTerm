import os
import re
import yaml
from typing import List, Dict, Optional


class CommandRulesResolver:
    """
    Evalúa comandos bash contra reglas declarativas regex (allow/ask/deny).

    Prioridad de reglas:
      1. Archivo workspace: .agents/command_rules.yaml
      2. Archivo de usuario: ~/.kogniterm/command_rules.yaml
      3. Reglas por defecto embebidas en código

    Acciones posibles:
      - allow: ejecutar sin confirmación interactiva
      - deny:  bloquear inmediatamente, sin preguntar al usuario
      - ask:   solicitar aprobación interactiva (comportamiento por defecto)
    """

    DEFAULT_RULES: List[Dict[str, str]] = [
        {"pattern": r"^git status$",           "action": "allow"},
        {"pattern": r"^git diff$",             "action": "allow"},
        {"pattern": r"^git log.*$",            "action": "allow"},
        {"pattern": r"^git branch.*$",         "action": "allow"},
        {"pattern": r"^ls(\s+.*)?$",           "action": "allow"},
        {"pattern": r"^pwd$",                  "action": "allow"},
        {"pattern": r"^whoami$",               "action": "allow"},
        {"pattern": r"^date$",                 "action": "allow"},
        {"pattern": r"^cat\s+.*$",             "action": "allow"},
        {"pattern": r"^echo\s+.*$",            "action": "allow"},
        {"pattern": r"^rm\s+-rf\s+.*$",        "action": "deny"},
        {"pattern": r"^rm\s+--recursive.*$",   "action": "deny"},
        {"pattern": r"^sudo\s+.*$",            "action": "deny"},
        {"pattern": r"^su\s+.*$",              "action": "deny"},
        {"pattern": r"^mkfs.*$",               "action": "deny"},
        {"pattern": r"^dd\s+.*$",              "action": "deny"},
        {"pattern": r"^chmod\s+777.*$",        "action": "deny"},
    ]

    def __init__(self, rules_file_path: Optional[str] = None):
        self.rules_file_path = rules_file_path
        self.rules: List[Dict[str, str]] = []
        self._loaded = False

    def load_rules(self):
        """Carga las reglas desde archivos de configuración y defaults."""
        self.rules = list(self.DEFAULT_RULES)
        self._loaded = True

        # Rutas de búsqueda de reglas de usuario
        if self.rules_file_path:
            path_candidates = [self.rules_file_path]
        else:
            path_candidates = [
                os.path.join(os.getcwd(), ".agents", "command_rules.yaml"),
                os.path.join(os.path.expanduser("~"), ".kogniterm", "command_rules.yaml"),
            ]

        for path in path_candidates:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                user_rules = data.get("rules", [])
                if user_rules:
                    # Reglas del usuario tienen mayor prioridad (se evalúan primero)
                    self.rules = user_rules + self.rules
                    break
            except Exception:
                import logging
                logging.getLogger(__name__).warning(
                    f"Error cargando reglas de comandos desde {path}"
                )

    def resolve(self, command: str) -> str:
        """
        Evalúa el comando y retorna la acción correspondiente.

        Returns:
            'allow' | 'deny' | 'ask'
        """
        if not self._loaded:
            self.load_rules()

        cmd_stripped = command.strip()
        for rule in self.rules:
            pattern = rule.get("pattern")
            action = rule.get("action")
            if pattern and action:
                try:
                    if re.match(pattern, cmd_stripped):
                        return action
                except re.error:
                    pass

        return "ask"  # acción por defecto
