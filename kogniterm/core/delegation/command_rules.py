import os
import re
import shlex
import yaml
from typing import List, Dict, Optional, Set

_SPLIT_RE = re.compile(r'(?:\|\||&&|\||;|\n)')
_WRAPPERS = {
    "sudo", "su", "bash", "sh", "zsh", "env", "nohup", "xargs",
    "watch", "timeout", "nice", "eval", "doas", "ssh"
}


def _segments(command: str) -> List[str]:
    parts = [p.strip() for p in _SPLIT_RE.split(command) if p.strip()]
    out = []
    for p in parts:
        for inner in re.findall(r'\$\(([^)]*)\)|`([^`]*)`', p):
            for candidate in inner:
                if candidate and isinstance(candidate, str) and candidate.strip():
                    out.extend(_segments(candidate))
        out.append(p)
        norm = _normalize(p)
        if norm and norm != p:
            out.append(norm)
    return [s for s in out if s]


_FLAGS_WITH_ARGS = {"-u", "-g", "-h", "-p", "-U", "-C", "-r", "-t", "-D", "-o", "-n"}
_CMD_STRING_FLAGS = {"-c", "--command"}


def _normalize(seg: str) -> str:
    try:
        tokens = shlex.split(seg)
    except ValueError:
        return seg.strip()
    if not tokens:
        return ""
    tokens[0] = tokens[0].rsplit("/", 1)[-1]
    while tokens and tokens[0] in _WRAPPERS and len(tokens) > 1:
        i = 1
        n = len(tokens)
        sub_tokens = None
        while i < n:
            token = tokens[i]
            if token in _CMD_STRING_FLAGS and i + 1 < n:
                cmd_str = tokens[i + 1]
                try:
                    sub_tokens = shlex.split(cmd_str) if " " in cmd_str else [cmd_str]
                except ValueError:
                    sub_tokens = [cmd_str]
                break
            elif token.startswith("-"):
                if token in _FLAGS_WITH_ARGS and i + 1 < n:
                    i += 2
                else:
                    i += 1
            else:
                sub_tokens = tokens[i:]
                break
        if not sub_tokens:
            break
        tokens = sub_tokens
        if tokens:
            tokens[0] = tokens[0].rsplit("/", 1)[-1]
    return " ".join(tokens)


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
        # DENY primero
        {"pattern": r"^rm\s+.*-[a-zA-Z]*[rR][a-zA-Z]*f|^rm\s+.*-[a-zA-Z]*f[a-zA-Z]*[rR]", "action": "deny"},
        {"pattern": r"^rm\s+--recursive", "action": "deny"},
        {"pattern": r"^(mkfs|fdisk|dd|shred)\b", "action": "deny"},
        {"pattern": r"^chmod\s+(777|-R\s+777)", "action": "deny"},
        {"pattern": r"^(nc|ncat|netcat)\b.*-e", "action": "deny"},
        {"pattern": r"^find\s+.*-delete", "action": "deny"},
        {"pattern": r"^:\(\)\s*\{", "action": "deny"},
        {"pattern": r"^(cat|less|more|head|tail|bat|strings)\s+.*(\.env|\.ssh|id_rsa|id_ed25519|/etc/shadow|credentials|\.pem|\.key|\.netrc|\.aws)", "action": "deny"},

        # ALLOW: anclados y sin metacaracteres / redirecciones
        {"pattern": r"^git (status|diff|log|branch)(\s+[\w\-./=]+)*$", "action": "allow"},
        {"pattern": r"^ls(\s+-[a-zA-Z]+)*(\s+[\w\-./]+)*$", "action": "allow"},
        {"pattern": r"^(pwd|whoami|date|uptime|id)$", "action": "allow"},
        {"pattern": r"^cat\s+[\w\-./]+$", "action": "allow"},
        {"pattern": r"^echo\s+[\w\s\-.,:'\"]+$", "action": "allow"},
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

        segments = _segments(command)
        if not segments:
            return "ask"

        actions: Set[str] = set()
        for seg in segments:
            matched = "ask"
            for rule in self.rules:
                pattern = rule.get("pattern")
                action = rule.get("action")
                if not (pattern and action):
                    continue
                try:
                    if re.match(pattern, seg):
                        matched = action
                        break
                except re.error:
                    continue
            actions.add(matched)

        if "deny" in actions:
            return "deny"  # deny-wins
        if actions == {"allow"}:
            return "allow"  # todos allow
        return "ask"  # fail-safe
