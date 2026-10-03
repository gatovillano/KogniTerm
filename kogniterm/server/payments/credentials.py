"""
Gestión de credenciales de los proveedores de pago.

Los secretos viven en un archivo **separado** del almacén de datos y con
permisos ``0600``. El módulo v1 los guardaba dentro de `payments_data.json`,
lo que significaba que cualquier volcado de estado (logs, backups, un
``GET /api/payments/...`` mal construido) filtraba las API keys.

Orden de resolución de cada credencial:

1. Variable de entorno (``STRIPE_SECRET_KEY``, ``MERCADOPAGO_ACCESS_TOKEN``...).
2. Archivo de credenciales ``~/.kogniterm/payments_credentials.json``.
3. ``None`` → el proveedor se considera no configurado.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import tempfile
from pathlib import Path
from typing import Dict, Optional

from kogniterm.server.payments.models import PaymentProviderType

logger = logging.getLogger("kogniterm.payments.credentials")

DEFAULT_CREDENTIALS_FILE = Path.home() / ".kogniterm" / "payments_credentials.json"

#: Variable de entorno → clave interna, por proveedor.
ENV_KEYS: Dict[PaymentProviderType, Dict[str, str]] = {
    PaymentProviderType.STRIPE: {
        "secret_key": "STRIPE_SECRET_KEY",
        "webhook_secret": "STRIPE_WEBHOOK_SECRET",
    },
    PaymentProviderType.MERCADOPAGO: {
        "secret_key": "MERCADOPAGO_ACCESS_TOKEN",
        "webhook_secret": "MERCADOPAGO_WEBHOOK_SECRET",
    },
    PaymentProviderType.MOCK: {
        "secret_key": "KOGNITERM_MOCK_ACCESS_TOKEN",
        "webhook_secret": "KOGNITERM_MOCK_WEBHOOK_SECRET",
    },
}


def resolve_credentials_file() -> Path:
    raw = os.getenv("KOGNITERM_PAYMENTS_CREDENTIALS_FILE")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return DEFAULT_CREDENTIALS_FILE


class CredentialStore:
    """Archivo de secretos independiente, escrito de forma atómica y 0600."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or resolve_credentials_file()
        self._data: Optional[Dict[str, dict]] = None

    # ── I/O ──────────────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, dict]:
        if self._data is not None:
            return self._data
        if not self.path.exists():
            self._data = {}
            return self._data
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._data = {
                provider: dict(value)
                for provider, value in (raw.get("providers") or {}).items()
                if isinstance(value, dict)
            }
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Archivo de credenciales ilegible (%s): %s", self.path, exc)
            self._data = {}
        return self._data

    def _save(self) -> None:
        payload = {"version": 1, "providers": self._load()}
        self.path.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ── API pública ──────────────────────────────────────────────────────────

    def set(
        self,
        provider: PaymentProviderType,
        *,
        secret_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        enabled: Optional[bool] = None,
        extra: Optional[Dict[str, str]] = None,
    ) -> None:
        data = self._load()
        entry = data.setdefault(provider.value, {})
        if secret_key is not None:
            entry["secret_key"] = secret_key
        if webhook_secret is not None:
            entry["webhook_secret"] = webhook_secret
        if enabled is not None:
            entry["enabled"] = enabled
        if extra:
            entry["extra"] = {**entry.get("extra", {}), **extra}
        entry.setdefault("enabled", True)
        self._data = data
        self._save()
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:  # pragma: no cover
            logger.debug("No se pudo ajustar el modo del archivo de credenciales")

    def resolve(self, provider: PaymentProviderType) -> Dict[str, str]:
        """Devuelve las credenciales efectivas (env > archivo), sin filtrar nada."""
        env_map = ENV_KEYS.get(provider, {})
        stored = self._load().get(provider.value, {}) or {}
        credentials: Dict[str, str] = {}

        for internal_key, env_name in env_map.items():
            value = os.getenv(env_name) or stored.get(internal_key)
            if value:
                credentials[internal_key] = value

        for key, value in stored.get("extra", {}).items():
            if value:
                credentials[key] = value

        credentials["enabled"] = "1" if stored.get("enabled", True) else "0"
        credentials["tolerance"] = str(
            os.getenv("KOGNITERM_WEBHOOK_TOLERANCE", "300")
        )
        return credentials

    def is_configured(self, provider: PaymentProviderType) -> bool:
        return bool(self.resolve(provider).get("secret_key"))

    def public_view(self) -> Dict[str, dict]:
        """Estado sin secretos, apto para la API."""
        return {
            p.value: {
                "configured": self.is_configured(p),
                "webhook_configured": bool(self.resolve(p).get("webhook_secret")),
                "enabled": self.resolve(p).get("enabled") == "1",
            }
            for p in PaymentProviderType
        }

    def mask(self, value: Optional[str]) -> str:
        if not value:
            return ""
        if len(value) <= 8:
            return "****"
        return f"{value[:4]}****{value[-4:]}"
