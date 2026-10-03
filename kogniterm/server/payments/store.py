"""
Almacén persistente del sistema de pagos.

Diseñado para un despliegue local (un usuario, un proceso) pero con garantías
de integridad ausentes en el módulo original:

* **Resolución perezosa** de la ruta: `KOGNITERM_PAYMENTS_FILE` se lee al
  construir el almacén, no al importar el módulo (el original leía el env
  var en tiempo de import y los tests escribían sobre el archivo real).
* **Escritura atómica**: se escribe a un temporal y se hace `os.replace`, de
  modo que un corte de energía nunca deja un JSON corrupto.
* **Permisos 0600**: los datos contienen saldos e identificadores de proveedor.
* **Lock de archivo (fcntl)**: serializa escrituras entre hilos/procesos.
* **Migración de esquema**: el v1 (formato del módulo anterior) se importa
  automáticamente sin perder transacciones.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from kogniterm.server.payments.catalog import default_settings_kwargs
from kogniterm.server.payments.errors import StorageError
from kogniterm.server.payments.models import (
    SCHEMA_VERSION,
    AuditEntry,
    CreditLedgerEntry,
    PaymentData,
    PaymentSettings,
    RefundRecord,
    TransactionRecord,
    UserSubscription,
    WebhookEvent,
)

logger = logging.getLogger("kogniterm.payments.storage")

DEFAULT_DATA_FILE = Path.home() / ".kogniterm" / "payments_data.json"


def resolve_data_file() -> Path:
    """Resuelve la ruta del almacén en el momento de la llamada.

    Se lee ``KOGNITERM_PAYMENTS_FILE`` aquí (y no a nivel de módulo) para que
    los tests y los despliegues multi-instancia puedan redirigir el almacén.
    """
    raw = os.getenv("KOGNITERM_PAYMENTS_FILE")
    if raw and raw.strip():
        return Path(raw).expanduser().resolve()
    return DEFAULT_DATA_FILE


class FileLock:
    """Lock entre procesos basado en ``fcntl.flock`` sobre un fichero aparte.

    Se usa un fichero ``.lock`` sibling porque el propio JSON se renombra de
    forma atómica (su inode cambia en cada escritura y flock se perdería).
    """

    def __init__(self, path: Path):
        self._path = path.with_suffix(path.suffix + ".lock")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fd: Optional[int] = None

    @contextmanager
    def acquire(self, timeout: float = 10.0) -> Iterator[None]:
        import fcntl

        fd = os.open(str(self._path), os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.time() + timeout
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.time() > deadline:
                        raise StorageError(
                            "No se pudo obtener el lock del almacén de pagos "
                            f"({self._path}); ¿otro proceso lo mantiene abierto?"
                        )
                    time.sleep(0.02)
            self._fd = fd
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
                self._fd = None

    def read_bytes_locked(self) -> Optional[bytes]:
        """Lectura sincrónica bajo lock (usado por la rotación de logs)."""
        if not self._path.exists():
            return None
        return self._path.read_bytes()


def _hash_audit(prev_hash: str, action: str, target: Optional[str], data: dict) -> str:
    payload = json.dumps(
        {"prev": prev_hash, "action": action, "target": target, "data": data},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class PaymentStore:
    """Repositorio con carga perezosa, escritura atómica y bitácora encadenada."""

    MAX_AUDIT_ENTRIES = 5000
    MAX_TRANSACTIONS = 5000

    def __init__(self, data_file: Optional[Path] = None):
        self._explicit_path = Path(data_file).expanduser() if data_file else None
        self.path = self._explicit_path or resolve_data_file()
        self.lock = FileLock(self.path)
        self._thread_lock = threading.RLock()
        self._data: Optional[PaymentData] = None

    # ── Acceso al documento ──────────────────────────────────────────────────

    @property
    def data(self) -> PaymentData:
        if self._data is None:
            self._data = self._load()
        return self._data

    def reload(self) -> PaymentData:
        with self._thread_lock:
            self._data = self._load()
            return self._data

    @contextmanager
    def transaction(self) -> Iterator[PaymentData]:
        """Context manager: muta el documento y persiste al salir sin excepción.

        Si el cuerpo lanza, los cambios en memoria se descartan recargando
        desde disco, de modo que no queden estados parciales.
        """
        with self._thread_lock:
            data = self.data
            snapshot = data.model_dump(mode="json")
            try:
                yield data
            except Exception:
                self._data = PaymentData.model_validate(snapshot)
                raise
            else:
                try:
                    self._flush(data)
                except Exception as exc:  # pragma: no cover - solo I/O
                    self._data = PaymentData.model_validate(snapshot)
                    raise StorageError(f"No se pudo guardar el estado de pagos: {exc}")

    # ── Persistencia ─────────────────────────────────────────────────────────

    def _load(self) -> PaymentData:
        if not self.path.exists():
            data = PaymentData(settings=PaymentSettings(**default_settings_kwargs()))
            self._atomic_write(data)
            return data

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            backup = self._quarantine_corrupt(str(exc))
            logger.error(
                "Almacén de pagos corrupto (%s). Se respaldó en %s y se reinició.",
                exc,
                backup,
            )
            return PaymentData(settings=PaymentSettings(**default_settings_kwargs()))

        data, migrated = self._migrate(raw)
        if migrated:
            # Reescribe inmediatamente: el archivo en disco aún contiene el
            # formato viejo, incluidos los secretos que el v1 guardaba dentro
            # de `settings`. Sin esta pasada, las claves seguirían en el disco
            # para siempre aunque el modelo en memoria ya las hubiera soltado.
            self._atomic_write(data)
            logger.info("Almacén de pagos migrado a esquema v%s en disco", SCHEMA_VERSION)
        return data

    def _migrate(self, raw: Dict[str, Any]) -> tuple[PaymentData, bool]:
        """Migra documentos de cualquier versión soportada al esquema actual.

        Devuelve ``(datos, hubo_migracion)``.
        """
        version = int(raw.get("schema_version", 1))

        if version >= SCHEMA_VERSION:
            try:
                return PaymentData.model_validate(raw), False
            except Exception as exc:
                logger.error("Documento de pagos con esquema %s inválido: %s", version, exc)
                return PaymentData(settings=PaymentSettings(**default_settings_kwargs())), True

        logger.info("Migrando almacén de pagos de esquema v%s a v%s", version, SCHEMA_VERSION)
        subs_raw = raw.get("subscriptions", {}) or {}
        txs_raw = raw.get("transactions", []) or []

        settings = PaymentSettings(**default_settings_kwargs())
        old_settings = raw.get("settings", {}) or {}

        # El v1 guardaba los secretos dentro de settings: se descartan aquí a
        # propósito, el usuario debe rotarlos y volver a configurarlos.
        plans = old_settings.get("plans")
        if plans:
            settings.plans = [PlanConfigAdapter.build(p) for p in plans]
        if old_settings.get("public_base_url"):
            settings.public_base_url = old_settings["public_base_url"]

        data = PaymentData(
            settings=settings,
            subscriptions={uid: _upgrade_subscription(sub) for uid, sub in subs_raw.items()},
            transactions=[_upgrade_transaction(tx) for tx in txs_raw],
        )
        return data, True

    def _quarantine_corrupt(self, reason: str) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{self.path.name}.corrupt-{stamp}")
        try:
            self.path.rename(backup)
            os.chmod(backup, 0o600)
        except OSError:  # pragma: no cover
            logger.exception("No se pudo aislar el almacén corrupto")
        return backup

    def _atomic_write(self, data: PaymentData) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data.model_dump(mode="json"), indent=2, ensure_ascii=False)

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp_name, 0o600)
            os.replace(tmp_name, self.path)
            try:
                dir_fd = os.open(str(self.path.parent), os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:  # pragma: no cover - no todos los FS lo soportan
                pass
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _flush(self, data: PaymentData) -> None:
        self._trim(data)
        with self.lock.acquire():
            self._atomic_write(data)

    @staticmethod
    def _trim(data: PaymentData) -> None:
        """Recorta las colecciones no acotadas para que el JSON no crezca sin fin."""
        if len(data.audit_log) > PaymentStore.MAX_AUDIT_ENTRIES:
            data.audit_log = data.audit_log[-PaymentStore.MAX_AUDIT_ENTRIES :]
        if len(data.credit_ledger) > PaymentStore.MAX_AUDIT_ENTRIES:
            data.credit_ledger = data.credit_ledger[-PaymentStore.MAX_AUDIT_ENTRIES :]
        if len(data.transactions) > PaymentStore.MAX_TRANSACTIONS:
            data.transactions = data.transactions[-PaymentStore.MAX_TRANSACTIONS :]

    # ── Índices derivados (recalculados en cada acceso; N es pequeño) ────────

    def find_transaction(self, tx_id: Optional[str] = None, **match: Any) -> Optional[TransactionRecord]:
        for tx in self.data.transactions:
            if tx_id and tx.id == tx_id:
                return tx
            if all(getattr(tx, key, None) == value for key, value in match.items()):
                return tx
        return None

    def transactions_for_user(self, user_id: str, limit: int = 100) -> List[TransactionRecord]:
        return [tx for tx in self.data.transactions if tx.user_id == user_id][-limit:][::-1]

    def get_subscription(self, user_id: str) -> Optional[UserSubscription]:
        return self.data.subscriptions.get(user_id)

    def ledger_for_user(self, user_id: str, limit: int = 50) -> List[CreditLedgerEntry]:
        return [e for e in self.data.credit_ledger if e.user_id == user_id][-limit:][::-1]

    # ── Auditoría encadenada ─────────────────────────────────────────────────

    def append_audit(
        self,
        action: str,
        *,
        target: Optional[str] = None,
        actor: str = "system",
        **data: Any,
    ) -> AuditEntry:
        log = self.data.audit_log
        prev = log[-1].hash if log else "0" * 16
        entry = AuditEntry(
            seq=len(log) + 1,
            actor=actor,
            action=action,
            target=target,
            data=data,
            prev_hash=prev,
        )
        entry.hash = _hash_audit(prev, action, target, data)
        log.append(entry)
        return entry

    def verify_audit_chain(self) -> Dict[str, Any]:
        """Verifica que la bitácora no fue editada fuera de la aplicación."""
        prev = "0" * 16
        for i, entry in enumerate(self.data.audit_log):
            if entry.prev_hash != prev:
                return {"valid": False, "broken_at": i, "reason": "prev_hash mismatch"}
            expected = _hash_audit(prev, entry.action, entry.target, entry.data)
            if entry.hash != expected:
                return {"valid": False, "broken_at": i, "reason": "hash mismatch"}
            prev = entry.hash
        return {"valid": True, "entries": len(self.data.audit_log)}


# ── Ayudas de migración ─────────────────────────────────────────────────────


class PlanConfigAdapter:
    """Adapta los planes de la v1 (sin `description`, sin `sort_order`)."""

    @staticmethod
    def build(raw: Dict[str, Any]) -> dict:
        from kogniterm.server.payments.models import PlanConfig

        raw = dict(raw)
        raw.setdefault("description", "")
        raw.setdefault("sort_order", 0)
        raw.pop("interval", None)
        raw["interval"] = {"month": "month", "year": "year", "one_time": "one_time"}.get(
            str(raw.get("interval", "month")), "month"
        )
        raw.setdefault("features", [])
        return PlanConfig.model_validate(raw)


def _upgrade_subscription(raw: Dict[str, Any]) -> UserSubscription:
    raw = dict(raw)
    raw.setdefault("status", "active")
    raw.setdefault("provider_customer_id", raw.get("stripe_customer_id") or raw.get("mercadopago_payer_id"))
    raw.setdefault("provider_subscription_id", raw.get("subscription_id"))
    if raw.get("subscription_id") and not raw.get("provider_subscription_id"):
        raw["provider_subscription_id"] = raw["subscription_id"]
    raw.setdefault("credits_granted_total", raw.get("credits_remaining", 0))
    raw.setdefault("credits_consumed_total", 0)
    raw.setdefault("provider", "mock")
    raw.setdefault("period_start", None)
    raw.setdefault("created_at", raw.get("updated_at", 0.0) or 0.0)
    raw.setdefault("metadata", {})
    return UserSubscription.model_validate(raw)


def _upgrade_transaction(raw: Dict[str, Any]) -> TransactionRecord:
    raw = dict(raw)
    raw.setdefault("kind", "subscription")
    raw.setdefault("currency", "USD")
    raw.setdefault("refunded_cents", 0)
    raw.setdefault("updated_at", raw.get("created_at", 0.0) or 0.0)
    return TransactionRecord.model_validate(raw)
