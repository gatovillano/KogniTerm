from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


class PaymentStore:
    """Persistencia JSON thread-safe para pagos y suscripciones."""

    def __init__(self, path: Optional[str] = None):
        default_path = Path.home() / ".kogniterm" / "payments.json"
        env_path = os.environ.get("KOGNITERM_PAYMENTS_DB")
        self.path = Path(path or env_path or str(default_path))
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = self._default_data()
        self._load()

    @staticmethod
    def _default_data() -> Dict[str, Any]:
        return {
            "subscriptions": {},
            "usage": {},
            "checkouts": {},
            "payments": [],
            "customers": {},
        }

    def _load(self) -> None:
        with self._lock:
            if self.path.exists():
                try:
                    loaded = json.loads(self.path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        base = self._default_data()
                        for k, v in base.items():
                            base[k] = loaded.get(k, v)
                        self._data = base
                except Exception:
                    self._data = self._default_data()
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def _save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)

    def get_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            val = self._data.get("subscriptions", {}).get(user_id)
            return deepcopy(val) if val is not None else None

    def set_subscription(self, user_id: str, sub: Dict[str, Any]) -> None:
        with self._lock:
            self._data.setdefault("subscriptions", {})[user_id] = deepcopy(sub)
            self._save()

    def get_usage(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._data.get("usage", {}).get(user_id, {}))

    def set_usage(self, user_id: str, usage: Dict[str, Any]) -> None:
        with self._lock:
            self._data.setdefault("usage", {})[user_id] = deepcopy(usage)
            self._save()

    def get_checkout(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            val = self._data.get("checkouts", {}).get(session_id)
            return deepcopy(val) if val is not None else None

    def set_checkout(self, session_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self._data.setdefault("checkouts", {})[session_id] = deepcopy(data)
            self._save()

    def add_payment(self, record: Dict[str, Any]) -> None:
        with self._lock:
            self._data.setdefault("payments", []).append(deepcopy(record))
            self._save()

    def list_payments(self, user_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [deepcopy(p) for p in self._data.get("payments", []) if p.get("user_id") == user_id]

    def clear(self) -> None:
        with self._lock:
            self._data = self._default_data()
            self._save()

    def raw(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._data)
