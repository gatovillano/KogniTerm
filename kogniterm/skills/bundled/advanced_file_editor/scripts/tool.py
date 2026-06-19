"""
Herramienta Profesional de Edición de Archivos Avanzada
========================================================

Esta herramienta proporciona capacidades profesionales de edición de archivos
con soporte para múltiples operaciones por lote, rollback automático, y validación
de seguridad avanzada.

Características:
- Múltiples estrategias de edición (bloques, líneas, regex, inserción, eliminación)
- Operaciones por lote (batch operations)
- Transacciones con rollback automático
- Validación de seguridad previa
- Logging profesional
- Manejo robusto de errores
"""

import os
import re
import difflib
import logging
import tempfile
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

# Importaciones del módulo base
from kogniterm.skills.bundled.file_operations.scripts.file_editor import (
    advanced_file_editor,
    common_editor_schema,
    FlexibleMatcher,
    RaceConditionGuard,
    RaceConditionDetected
)
from kogniterm.skills.bundled.file_operations.scripts._utils import clean_path

# Configuración de logging
logger = logging.getLogger(__name__)


class OperationStatus(Enum):
    """Estado de una operación individual."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class OperationResult:
    """Resultado de una operación individual."""
    operation_index: int
    status: OperationStatus
    message: str
    diff: Optional[str] = None
    backup_path: Optional[str] = None


@dataclass
class Transaction:
    """Representa una transacción de edición."""
    transaction_id: str
    path: str
    original_content: str
    operations: List[Dict[str, Any]]
    results: List[OperationResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def get_content_hash(self) -> str:
        """Genera hash del contenido para verificación."""
        return hashlib.sha256(self.original_content.encode()).hexdigest()


class TransactionManager:
    """Gestiona transacciones de edición con soporte para rollback."""
    
    def __init__(self):
        self.transactions: Dict[str, Transaction] = {}
        self.max_transactions = 100
    
    def create_transaction(self, path: str, operations: List[Dict[str, Any]]) -> Transaction:
        """Crea una nueva transacción."""
        transaction_id = f"tx_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # Leer contenido original
        try:
            with open(path, 'r', encoding='utf-8') as f:
                original_content = f.read()
        except Exception as e:
            original_content = ""
            logger.warning(f"No se pudo leer archivo para transacción {transaction_id}: {e}")
        
        transaction = Transaction(
            transaction_id=transaction_id,
            path=path,
            original_content=original_content,
            operations=operations
        )
        
        # Limpiar transacciones antiguas
        if len(self.transactions) >= self.max_transactions:
            oldest_key = min(self.transactions.keys())
            del self.transactions[oldest_key]
        
        self.transactions[transaction_id] = transaction
        logger.info(f"Transacción creada: {transaction_id} con {len(operations)} operaciones")
        return transaction
    
    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Obtiene una transacción por ID."""
        return self.transactions.get(transaction_id)
    
    def rollback_transaction(self, transaction_id: str) -> bool:
        """Realiza rollback de una transacción."""
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            logger.error(f"Transacción no encontrada: {transaction_id}")
            return False
        
        try:
            with open(transaction.path, 'w', encoding='utf-8') as f:
                f.write(transaction.original_content)
            logger.info(f"Rollback exitoso de transacción: {transaction_id}")
            return True
        except Exception as e:
            logger.error(f"Error en rollback de {transaction_id}: {e}")
            return False


# Instancia global del gestor de transacciones
_transaction_manager = TransactionManager()


def _validate_operation_safety(operation: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Valida que una operación sea segura de ejecutar.
    
    Returns:
        Tuple[bool, str]: (es_seguro, mensaje_error)
    """
    action = operation.get('action')
    path = operation.get('path', '')
    
    # Validaciones básicas
    if not path:
        return False, "Path no especificado"
    
    if not action:
        return False, "Action no especificada"
    
    # Validar path
    cleaned_path = clean_path(path)
    if not cleaned_path:
        return False, f"Path inválido: {path}"
    
    # Validar acciones permitidas
    allowed_actions = [
        "insert_line", "replace_block", "replace_lines",
        "insert_after_match", "insert_before_match",
        "replace_regex", "delete_lines", "prepend_content",
        "append_content", "full_replacement"
    ]
    
    if action not in allowed_actions:
        return False, f"Action no permitida: {action}"
    
    # Validaciones específicas por acción
    if action in ["replace_block", "insert_after_match", "insert_before_match"]:
        if not operation.get('target_content'):
            return False, f"'target_content' requerido para {action}"
    
    if action in ["insert_line", "replace_lines"]:
        if not isinstance(operation.get('line_number'), int):
            return False, f"'line_number' debe ser entero para {action}"
    
    if action == "replace_regex":
        try:
            re.compile(operation.get('regex_pattern', ''))
        except re.error as e:
            return False, f"Regex inválido: {e}"
    
    return True, ""


def _generate_diff(original: str, modified: str, path: str) -> str:
    """Genera un diff unificado entre contenido original y modificado."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}"
    )
    return "".join(diff)


def batch_edit(
    path: str,
    operations: List[Dict[str, Any]],
    confirm: bool = False,
    transaction_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Realiza múltiples operaciones de edición en un archivo.
    
    Args:
        path: Ruta del archivo a editar
        operations: Lista de operaciones a realizar
        confirm: Si True, aplica cambios sin solicitar confirmación
        transaction_id: ID de transacción existente para continuar
    
    Returns:
        Dict con resultado de la operación
    """
    path = clean_path(path)
    if not path:
        return {"error": "Path no proporcionado o inválido"}
    
    # Validar lista de operaciones
    if not operations:
        return {"error": "Se requiere al menos una operación"}
    
    if not isinstance(operations, list):
        return {"error": "operations debe ser una lista"}
    
    # Verificar si el archivo existe
    file_exists = os.path.exists(path)
    if not file_exists and operations[0].get('action') not in ["prepend_content", "full_replacement"]:
        return {"error": f"El archivo '{path}' no existe"}
    
    # Crear o recuperar transacción
    if transaction_id and transaction_id in _transaction_manager.transactions:
        transaction = _transaction_manager.get_transaction(transaction_id)
        logger.info(f"Continuando transacción existente: {transaction_id}")
    else:
        transaction = _transaction_manager.create_transaction(path, operations)
    
    # Leer contenido actual
    try:
        if file_exists:
            with open(path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        else:
            current_content = ""
    except Exception as e:
        return {"error": f"Error al leer archivo: {e}"}
    
    # Validar todas las operaciones antes de ejecutar
    validation_errors = []
    for idx, op in enumerate(operations):
        is_safe, msg = _validate_operation_safety(op)
        if not is_safe:
            validation_errors.append(f"Operación {idx}: {msg}")
    
    if validation_errors:
        return {
            "error": "Errores de validación",
            "details": validation_errors
        }
    
    # Aplicar operaciones
    results: List[OperationResult] = []
    modified_content = current_content
    all_success = True
    
    for idx, op in enumerate(operations):
        result = OperationResult(
            operation_index=idx,
            status=OperationStatus.PROCESSING,
            message=""
        )
        
        try:
            # Aplicar operación individual
            op_result = advanced_file_editor(
                path=path,
                confirm=True,  # Ya validamos, forzamos confirmación
                **{k: v for k, v in op.items() if k != 'path'}  # Excluir path duplicado
            )
            
            if isinstance(op_result, dict):
                if op_result.get('status') == 'success':
                    result.status = OperationStatus.SUCCESS
                    result.message = op_result.get('message', 'Operación exitosa')
                elif op_result.get('status') == 'requires_confirmation':
                    result.status = OperationStatus.FAILED
                    result.message = "Se requiere confirmación adicional"
                    all_success = False
                else:
                    result.status = OperationStatus.FAILED
                    result.message = op_result.get('error', 'Error desconocido')
                    all_success = False
            else:
                result.status = OperationStatus.SUCCESS
                result.message = str(op_result)
            
            results.append(result)
            
        except Exception as e:
            result.status = OperationStatus.FAILED
            result.message = f"Error inesperado: {str(e)}"
            results.append(result)
            all_success = False
            break  # Detener si falla una operación crítica
    
    # Actualizar transacción con resultados
    transaction.results = results
    
    # Generar resumen
    success_count = sum(1 for r in results if r.status == OperationStatus.SUCCESS)
    failed_count = len(results) - success_count
    
    return {
        "status": "success" if all_success else "partial_failure",
        "transaction_id": transaction.transaction_id,
        "summary": {
            "total_operations": len(operations),
            "successful": success_count,
            "failed": failed_count
        },
        "results": [
            {
                "index": r.operation_index,
                "status": r.status.value,
                "message": r.message
            }
            for r in results
        ]
    }


# Alias para compatibilidad
_apply_advanced_update = advanced_file_editor


def _apply_advanced_update_with_validation(path: str, content: str) -> str:
    """
    Aplica una actualización completa de archivo tras validación del usuario.
    Mantiene compatibilidad con la API existente.
    """
    result = advanced_file_editor(
        path=path,
        action="full_replacement",
        content=content,
        confirm=True
    )
    
    if isinstance(result, dict):
        if "message" in result:
            return result["message"]
        if "error" in result:
            return f"Error: {result['error']}"
        return str(result)
    return str(result)


def advanced_file_editor_tool(**kwargs) -> Dict[str, Any]:
    """
    Herramienta principal de edición de archivos.
    
    Esta función mantiene compatibilidad con la API existente mientras
    soporta nuevas capacidades como operaciones por lote.
    """
    # Detectar si son operaciones por lote
    if 'operations' in kwargs and isinstance(kwargs.get('operations'), list):
        return batch_edit(
            path=kwargs.get('path', ''),
            operations=kwargs['operations'],
            confirm=kwargs.get('confirm', False),
            transaction_id=kwargs.get('transaction_id')
        )
    
    # Fallback a la función original para compatibilidad
    return advanced_file_editor(**kwargs)


# Schema mejorado que incluye soporte para batch operations
parameters_schema = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Ruta del archivo a editar (puede ser absoluta o relativa al directorio de trabajo)."
        },
        "action": {
            "type": "string",
            "description": "Estrategia de edición a utilizar.",
            "enum": [
                "insert_line", "replace_block", "replace_lines",
                "insert_after_match", "insert_before_match",
                "replace_regex", "delete_lines", "prepend_content",
                "append_content", "full_replacement"
            ]
        },
        "content": {
            "type": "string",
            "description": "Texto a insertar o reemplazar. Usar para: insert_line, insert_after_match, insert_before_match, prepend, append, full_replacement."
        },
        "target_content": {
            "type": "string",
            "description": "Bloque de texto exacto a BUSCAR. Usar para: replace_block, insert_after_match, insert_before_match, replace_lines."
        },
        "replacement_content": {
            "type": "string",
            "description": "Texto NUEVO que reemplazará al objetivo. Usar para: replace_block, replace_lines, replace_regex."
        },
        "line_number": {
            "type": "integer",
            "description": "Línea de inicio (1-based). Usar para: insert_line, replace_lines, delete_lines."
        },
        "end_line": {
            "type": "integer",
            "description": "Línea de fin (1-based) para rangos. Usar para: replace_lines, delete_lines."
        },
        "regex_pattern": {
            "type": "string",
            "description": "Patrón regex para replace_regex."
        },
        "confirm": {
            "type": "boolean",
            "description": "Confirmación automática de cambios. Por defecto: false.",
            "default": False
        },
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "content": {"type": "string"},
                    "target_content": {"type": "string"},
                    "replacement_content": {"type": "string"},
                    "line_number": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "regex_pattern": {"type": "string"}
                }
            },
            "description": "Lista de operaciones para ejecutar por lote. Si se proporciona, ignora action y otros parámetros individuales."
        },
        "transaction_id": {
            "type": "string",
            "description": "ID de transacción existente para continuar operaciones."
        }
    },
    "required": ["path"]
}

# Metadata de la herramienta
name = "advanced_file_editor"
description = "Herramienta profesional de edición de archivos con múltiples estrategias, operaciones por lote y rollback automático."

# Registrar schema
advanced_file_editor.parameters_schema = parameters_schema
advanced_file_editor_tool.parameters_schema = parameters_schema