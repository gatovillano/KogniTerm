"""
Advanced File Editor - Herramienta Profesional de Edicion
=========================================================

Cambios (2026-07) - atomicidad real:
- batch_edit ahora valida TODAS las operaciones contra el contenido
  en memoria ANTES de escribir. Si alguna falla, el archivo en disco
  queda intacto. Antes escribia a disco por cada operacion, dejando
  estados parciales.
- El "rollback" original se mantiene para sesiones que ya invocaron
  una transaccion. Pero el flujo normal es atomico por diseno, no
  por recuperacion.
- Se anade `action: "rollback"` explicito en single-op para revertir
  una transaccion por su transaction_id.
- Se anade `advanced_file_editor_tool` que detecta batch vs single
  y delega correctamente.
"""

import os
import re
import difflib
import logging
import hashlib
import shutil
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

# Importaciones del modulo base via importlib (los directorios con guiones
# no pueden importarse con la sintaxis de puntos de Python)
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_file_operations():
    """Carga modulos desde la skill hermana file-operations via importlib."""
    this_dir = Path(__file__).resolve().parent
    bundled_dir = this_dir.parent
    file_ops_scripts = bundled_dir / "file-operations" / "scripts"

    parent_pkg_name = "_file_ops_scripts_pkg"
    if parent_pkg_name not in sys.modules:
        parent_pkg = ModuleType(parent_pkg_name)
        parent_pkg.__path__ = [str(file_ops_scripts)]
        sys.modules[parent_pkg_name] = parent_pkg

    utils_path = file_ops_scripts / "_utils.py"
    utils_spec = importlib.util.spec_from_file_location(
        f"{parent_pkg_name}._utils", str(utils_path)
    )
    utils_module = importlib.util.module_from_spec(utils_spec)
    utils_module.__package__ = parent_pkg_name
    sys.modules[f"{parent_pkg_name}._utils"] = utils_module
    utils_spec.loader.exec_module(utils_module)

    editor_path = file_ops_scripts / "file_editor.py"
    editor_spec = importlib.util.spec_from_file_location(
        f"{parent_pkg_name}.file_editor", str(editor_path),
        submodule_search_locations=[str(file_ops_scripts)]
    )
    editor_module = importlib.util.module_from_spec(editor_spec)
    editor_module.__package__ = parent_pkg_name
    sys.modules[f"{parent_pkg_name}.file_editor"] = editor_module
    editor_spec.loader.exec_module(editor_module)

    return editor_module, utils_module


_editor_module, _utils_module = _load_file_operations()

advanced_file_editor = _editor_module.advanced_file_editor
common_editor_schema = _editor_module.common_editor_schema
FlexibleMatcher = _editor_module.FlexibleMatcher
MultipleMatchesError = _editor_module.MultipleMatchesError
_apply_operation_pure = _editor_module._apply_operation_pure
RaceConditionGuard = _editor_module.RaceConditionGuard
RaceConditionDetected = _editor_module.RaceConditionDetected
clean_path = _utils_module.clean_path

logger = logging.getLogger(__name__)


class OperationStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # operacion valida pero no aplicable (no_changes)


@dataclass
class OperationResult:
    operation_index: int
    status: OperationStatus
    message: str
    matched_span: Optional[Dict[str, Any]] = None
    diff: Optional[str] = None


@dataclass
class Transaction:
    transaction_id: str
    path: str
    original_content: str
    backup_path: Optional[str]
    operations: List[Dict[str, Any]]
    results: List[OperationResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    applied: bool = False

    def get_content_hash(self) -> str:
        return hashlib.sha256(self.original_content.encode()).hexdigest()


class TransactionManager:
    """Gestiona transacciones con backup pre-aplicacion y rollback."""

    def __init__(self):
        self.transactions: Dict[str, Transaction] = {}
        self.max_transactions = 100

    def create_transaction(
        self, path: str, operations: List[Dict[str, Any]]
    ) -> Transaction:
        transaction_id = f"tx_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    original_content = f.read()
            else:
                original_content = ""
        except Exception as e:
            logger.warning(f"No se pudo leer archivo para {transaction_id}: {e}")
            original_content = ""

        # Backup pre-batch: se crea SIEMPRE al crear la transaccion, no al aplicar.
        # Asi, si el batch falla, hay un punto de retorno aunque la tx sea nueva.
        backup_path: Optional[str] = None
        if os.path.exists(path):
            try:
                backup_path = _make_backup_path(path, transaction_id)
                shutil.copy2(path, backup_path)
            except Exception as e:
                logger.warning(f"No se pudo crear backup para {transaction_id}: {e}")

        transaction = Transaction(
            transaction_id=transaction_id,
            path=path,
            original_content=original_content,
            backup_path=backup_path,
            operations=list(operations),
        )

        if len(self.transactions) >= self.max_transactions:
            oldest_key = min(self.transactions.keys())
            del self.transactions[oldest_key]

        self.transactions[transaction_id] = transaction
        logger.info(
            f"Transaccion creada: {transaction_id} con {len(operations)} operaciones, "
            f"backup: {backup_path}"
        )
        return transaction

    def rollback_transaction(self, transaction_id: str) -> bool:
        """Revierte el archivo al estado pre-batch."""
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            logger.error(f"Transaccion no encontrada: {transaction_id}")
            return False
        try:
            with open(transaction.path, "w", encoding="utf-8") as f:
                f.write(transaction.original_content)
            logger.info(f"Rollback exitoso: {transaction_id}")
            return True
        except Exception as e:
            logger.error(f"Error en rollback {transaction_id}: {e}")
            return False


def _make_backup_path(path: str, transaction_id: str) -> str:
    """Crea una ruta de backup en /tmp/kogniterm_rollback_<tx>_<ts>.bak."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = os.path.basename(path) or "file"
    return os.path.join(
        tempfile.gettempdir(),
        f"kogniterm_rollback_{transaction_id}_{base}_{ts}.bak",
    )


# Instancia global
_transaction_manager = TransactionManager()


def _validate_operation_safety(operation: Dict[str, Any], path_context: str = "") -> Tuple[bool, str]:
    """Validacion estatica previa a aplicar (estructura, no contenido)."""
    action = operation.get("action")
    path = operation.get("path", path_context)

    if not path:
        return False, "Path no especificado (ni en operacion ni en contexto)"
    if not action:
        return False, "Action no especificada"
    if not clean_path(path):
        return False, f"Path invalido: {path}"

    allowed = [
        "insert_line", "replace_block", "replace_lines",
        "insert_after_match", "insert_before_match",
        "replace_regex", "delete_lines", "prepend_content",
        "append_content", "full_replacement",
    ]
    if action not in allowed:
        return False, f"Action no permitida: {action}"

    if action in ("replace_block", "insert_after_match", "insert_before_match"):
        if not operation.get("target_content"):
            return False, f"'target_content' requerido para {action}"

    if action in ("insert_line", "replace_lines", "delete_lines"):
        if not isinstance(operation.get("line_number"), int):
            return False, f"'line_number' debe ser entero para {action}"

    if action == "replace_regex":
        try:
            re.compile(operation.get("regex_pattern", ""))
        except re.error as e:
            return False, f"Regex invalido: {e}"

    return True, ""


def _generate_diff(original: str, modified: str, path: str) -> str:
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    return "".join(difflib.unified_diff(
        original_lines, modified_lines,
        fromfile=f"a/{path}", tofile=f"b/{path}",
    ))


def batch_edit(
    path: str,
    operations: List[Dict[str, Any]],
    confirm: bool = False,
    transaction_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Aplica multiples operaciones de forma ATOMICA.

    Cambios 2026-07:
    - Valida TODAS las operaciones contra el contenido en memoria
      ANTES de escribir. Si cualquiera falla, el archivo en disco
      queda IDENTICO al original (atomicidad real).
    - Backup pre-batch en /tmp/kogniterm_rollback_*.bak al CREAR la
      transaccion, no al aplicar.
    - Cada operacion devuelve matched_span y diff en el resultado.

    Args:
        path: ruta del archivo
        operations: lista de operaciones (sin 'path' en cada una)
        confirm: si True, escribe sin pedir confirmacion
        transaction_id: id de una transaccion ya creada (continuacion)
    """
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado o invalido"}
    if not operations:
        return {"error": "Se requiere al menos una operacion"}
    if not isinstance(operations, list):
        return {"error": "operations debe ser una lista"}

    # Validacion estatica (estructura).
    validation_errors: List[str] = []
    for idx, op in enumerate(operations):
        is_safe, msg = _validate_operation_safety(op, path_context=path)
        if not is_safe:
            validation_errors.append(f"Operacion {idx}: {msg}")
    if validation_errors:
        return {"error": "Errores de validacion", "details": validation_errors}

    # Crear o recuperar transaccion. El backup se crea AQUI, antes de
    # cualquier escritura, para que un fallo total sea recuperable.
    if transaction_id and transaction_id in _transaction_manager.transactions:
        transaction = _transaction_manager.get_transaction(transaction_id)
        logger.info(f"Continuando transaccion existente: {transaction_id}")
    else:
        transaction = _transaction_manager.create_transaction(path, operations)

    # Verificar que el archivo no haya cambiado desde que se creo la tx.
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                current_on_disk = f.read()
        else:
            current_on_disk = ""
    except Exception as e:
        return {"error": f"Error al leer archivo: {e}"}

    if transaction.original_content != current_on_disk:
        return {
            "error": "El archivo en disco cambio desde que se creo la transaccion. "
                     "Re-lea el archivo y vuelva a intentar.",
            "transaction_id": transaction.transaction_id,
        }

    # ---- VALIDAR TODAS LAS OPERACIONES EN MEMORIA ----
    current_content = current_on_disk
    results: List[OperationResult] = []
    for idx, op in enumerate(operations):
        op_no_path = {k: v for k, v in op.items() if k != "path"}
        try:
            new_content, matched_span = _apply_operation_pure(current_content, op_no_path)
        except ValueError as e:
            # FALLO de validacion: NO escribimos nada en disco.
            results.append(OperationResult(
                operation_index=idx,
                status=OperationStatus.FAILED,
                message=str(e),
            ))
            return {
                "status": "rolled_back",
                "transaction_id": transaction.transaction_id,
                "atomic": True,
                "summary": {
                    "total_operations": len(operations),
                    "validated": idx,
                    "failed_at": idx,
                    "successful": 0,
                    "failed": 1,
                },
                "results": [
                    {
                        "index": r.operation_index,
                        "status": r.status.value,
                        "message": r.message,
                        "matched_span": r.matched_span,
                    }
                    for r in results
                ],
                "message": (
                    f"Operacion {idx} fallo: {results[-1].message}. "
                    f"Ningun cambio fue escrito al archivo (atomicidad)."
                ),
            }
        # OK: acumulamos el diff parcial y seguimos con la siguiente op.
        diff = _generate_diff(current_content, new_content, path)
        results.append(OperationResult(
            operation_index=idx,
            status=OperationStatus.SUCCESS,
            message="OK",
            matched_span=matched_span,
            diff=diff,
        ))
        current_content = new_content

    # ---- TODAS VALIDADAS ----
    final_diff = _generate_diff(transaction.original_content, current_content, path)
    if not final_diff:
        return {
            "status": "no_changes",
            "transaction_id": transaction.transaction_id,
            "message": "Ninguna operacion produjo cambios.",
        }

    if not confirm:
        # Devolvemos preview para confirmar.
        transaction.results = results
        return {
            "status": "requires_confirmation",
            "transaction_id": transaction.transaction_id,
            "atomic": True,
            "operation": "advanced_file_editor_tool",
            "args": {
                "path": path,
                "operations": operations,
                "confirm": True,
                "transaction_id": transaction.transaction_id,
            },
            "diff": final_diff,
            "summary": {
                "total_operations": len(operations),
                "validated": len(operations),
                "successful": 0,  # todavia no escrito
                "failed": 0,
            },
        }

    # ---- ESCRIBIR UNA SOLA VEZ ----
    agent_state = getattr(advanced_file_editor, "agent_state", None)
    if agent_state and os.path.exists(path):
        try:
            is_safe, msg = RaceConditionGuard.validate_write(
                agent_state, path, transaction.original_content
            )
            if not is_safe:
                return {"status": "error", "message": f"RACE CONDITION DETECTADA: {msg}"}
        except Exception as e:
            logger.warning(f"Error en Race Condition Guard: {e}")

    try:
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(current_content)

        if agent_state:
            RaceConditionGuard.register_write(agent_state, path, current_content)

        transaction.applied = True
        transaction.results = results

        success_count = sum(1 for r in results if r.status == OperationStatus.SUCCESS)
        return {
            "status": "success",
            "transaction_id": transaction.transaction_id,
            "atomic": True,
            "backup_path": transaction.backup_path,
            "summary": {
                "total_operations": len(operations),
                "validated": len(operations),
                "successful": success_count,
                "failed": 0,
            },
            "applied_diff": final_diff,
            "results": [
                {
                    "index": r.operation_index,
                    "status": r.status.value,
                    "message": r.message,
                    "matched_span": r.matched_span,
                    "diff": r.diff,
                }
                for r in results
            ],
        }
    except Exception as e:
        return {"status": "error", "message": f"Error al escribir cambios: {e}"}


# Alias para compatibilidad historica
_apply_advanced_update = advanced_file_editor


def _apply_advanced_update_with_validation(path: str, content: str) -> str:
    result = advanced_file_editor(
        path=path,
        action="full_replacement",
        content=content,
        confirm=True,
    )
    if isinstance(result, dict):
        if "message" in result:
            return result["message"]
        if "error" in result:
            return f"Error: {result['error']}"
        return str(result)
    return str(result)


def advanced_file_editor_tool(**kwargs) -> Dict[str, Any]:
    """Punto de entrada principal. Despacha a batch o single segun kwargs."""
    if "operations" in kwargs and isinstance(kwargs.get("operations"), list):
        return batch_edit(
            path=kwargs.get("path", ""),
            operations=kwargs["operations"],
            confirm=kwargs.get("confirm", False),
            transaction_id=kwargs.get("transaction_id"),
        )
    return advanced_file_editor(**kwargs)


# Schema con batch + rollback explicito.
parameters_schema = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Ruta del archivo (absoluta o relativa al cwd)."},
        "action": {
            "type": "string",
            "description": "Estrategia de edicion (single-op).",
            "enum": [
                "insert_line", "replace_block", "replace_lines",
                "insert_after_match", "insert_before_match",
                "replace_regex", "delete_lines", "prepend_content",
                "append_content", "full_replacement", "rollback",
            ],
        },
        "content": {"type": "string", "description": "Texto a insertar (insert_*, prepend, append, full_replacement)."},
        "target_content": {"type": "string", "description": "Bloque a BUSCAR (replace_block, insert_*_match, replace_lines)."},
        "replacement_content": {"type": "string", "description": "Texto NUEVO (replace_block, replace_lines, replace_regex)."},
        "line_number": {"type": "integer", "description": "Linea inicial 1-based."},
        "end_line": {"type": "integer", "description": "Linea final 1-based para rangos."},
        "regex_pattern": {"type": "string", "description": "Patron regex para replace_regex."},
        "fuzzy": {"type": "boolean", "description": "Permitir match flexible. Default: false.", "default": False},
        "require_unique": {"type": "boolean", "description": "Exigir match unico. Default: true.", "default": True},
        "context_hint": {"type": "string", "description": "Substring cercano para desambiguar."},
        "confirm": {"type": "boolean", "description": "Confirmacion automatica.", "default": False},
        "operations": {
            "type": "array",
            "description": (
                "Lista de operaciones para ejecucion ATOMICA. Si se "
                "proporciona, se ignoran 'action' y los demas parametros "
                "individuales. La ejecucion es todo-o-nada: si UNA op "
                "falla, NINGUN cambio se persiste en disco."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "content": {"type": "string"},
                    "target_content": {"type": "string"},
                    "replacement_content": {"type": "string"},
                    "line_number": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "regex_pattern": {"type": "string"},
                    "fuzzy": {"type": "boolean"},
                    "require_unique": {"type": "boolean"},
                    "context_hint": {"type": "string"},
                },
            },
        },
        "transaction_id": {"type": "string", "description": "ID de transaccion (continuar o rollback)."},
    },
    "required": ["path"],
}

name = "advanced_file_editor"
description = (
    "Herramienta profesional de edicion de archivos con multiples "
    "estrategias, operaciones por lote ATOMICAS (todo-o-nada) y "
    "rollback automatico via transaction_id. Match exacto por "
    "defecto; fuzzy solo opt-in con fuzzy=true."
)

advanced_file_editor.parameters_schema = parameters_schema
advanced_file_editor_tool.parameters_schema = parameters_schema
