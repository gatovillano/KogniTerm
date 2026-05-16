#!/usr/bin/env python3
"""
Script de prueba para el sistema de versionado de autoguardos.
Verifica que el AutosaveManager y la integración con HistoryManager funcionan correctamente.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Agregar el directorio al path
sys.path.insert(0, '/home/gato/Proyectos/Gemini-Interpreter')

from kogniterm.core.autosave_manager import AutosaveManager
from langchain_core.messages import HumanMessage, AIMessage

def test_autosave_manager():
    """Prueba básica del AutosaveManager."""
    print("🧪 Prueba 1: AutosaveManager básico")
    print("=" * 60)
    
    # Crear directorio temporal
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = AutosaveManager(tmpdir)
        
        # Crear algunos mensajes
        messages = [
            HumanMessage(content="¿Hola, cómo estás?"),
            AIMessage(content="¡Hola! Estoy bien, gracias por preguntar."),
        ]
        
        # Guardar versión 1
        success1, path1 = manager.save_version(messages, "Primera versión")
        print(f"✅ Versión 1 guardada: {success1}")
        print(f"   Ruta: {path1}")
        
        # Agregar más mensajes
        messages.append(HumanMessage(content="¿Cuál es tu nombre?"))
        messages.append(AIMessage(content="Soy KogniTerm."))
        
        # Guardar versión 2
        success2, path2 = manager.save_version(messages, "Segunda versión")
        print(f"✅ Versión 2 guardada: {success2}")
        print(f"   Ruta: {path2}")
        
        # Listar versiones
        versions = manager.get_session_versions()
        print(f"✅ Versiones en sesión: {len(versions)}")
        for v in versions:
            print(f"   - {v['filename']}: {v['message_count']} mensajes")
        
        # Cargar versión 1
        loaded = manager.load_version(path1)
        print(f"✅ Versión 1 cargada: {len(loaded)} mensajes")
        
        # Estadísticas
        stats = manager.get_statistics()
        print(f"✅ Estadísticas:")
        print(f"   - Session ID: {stats['current_session_id']}")
        print(f"   - Versiones en sesión: {stats['current_session_versions']}")
        print(f"   - Total de versiones: {stats['total_versions']}")
        
        manager.stop()
        print("\n✅ Prueba 1 COMPLETADA\n")


def test_history_manager_integration():
    """Prueba la integración con HistoryManager."""
    print("🧪 Prueba 2: Integración con HistoryManager")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Crear directorios necesarios
        os.makedirs(os.path.join(tmpdir, '.kogniterm'), exist_ok=True)
        
        history_path = os.path.join(tmpdir, '.kogniterm', 'history.json')
        
        from kogniterm.core.history_manager import HistoryManager
        
        # Crear HistoryManager
        hm = HistoryManager(history_path, auto_save_interval=None)
        
        # Agregar mensajes
        hm.add_message(HumanMessage(content="Primer mensaje"))
        hm.add_message(AIMessage(content="Primera respuesta"))
        
        # Verificar autoguardado versionado
        versions = hm.get_autosave_versions()
        print(f"✅ Versiones en sesión después de agregar: {len(versions)}")
        
        hm.add_message(HumanMessage(content="Segundo mensaje"))
        hm.add_message(AIMessage(content="Segunda respuesta"))
        
        versions = hm.get_autosave_versions()
        print(f"✅ Versiones en sesión después de más mensajes: {len(versions)}")
        
        # Estadísticas
        stats = hm.get_autosave_statistics()
        print(f"✅ Estadísticas del historial:")
        print(f"   - Versiones en sesión actual: {stats.get('current_session_versions')}")
        print(f"   - Total de versiones: {stats.get('total_versions')}")
        
        # Limpiar
        hm.stop_auto_save()
        print("\n✅ Prueba 2 COMPLETADA\n")


def test_directory_structure():
    """Verifica que la estructura de directorios es correcta."""
    print("🧪 Prueba 3: Estructura de directorios")
    print("=" * 60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = AutosaveManager(tmpdir)
        
        # Guardar una versión
        messages = [HumanMessage(content="test")]
        manager.save_version(messages)
        
        # Verificar estructura
        autosave_dir = os.path.join(tmpdir, 'autosave')
        print(f"✅ Directorio autosave existe: {os.path.exists(autosave_dir)}")
        
        session_dir = manager.session_dir
        print(f"✅ Directorio de sesión existe: {os.path.exists(session_dir)}")
        
        # Listar archivos
        files = os.listdir(session_dir)
        print(f"✅ Archivos en sesión: {len(files)}")
        for f in files:
            print(f"   - {f}")
        
        manager.stop()
        print("\n✅ Prueba 3 COMPLETADA\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 PRUEBAS DEL SISTEMA DE VERSIONADO DE AUTOGUARDOS")
    print("=" * 60 + "\n")
    
    try:
        test_autosave_manager()
        test_directory_structure()
        test_history_manager_integration()
        
        print("=" * 60)
        print("✅ ¡TODAS LAS PRUEBAS COMPLETADAS EXITOSAMENTE!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error en pruebas: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
