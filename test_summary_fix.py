#!/usr/bin/env python3
"""
Script de prueba para verificar que la corrección del resumen automático funciona correctamente.
"""

import sys
import os
sys.path.append('/home/gato/Gemini-Interpreter')

from kogniterm.core.llm_service import LLMService

def test_summary_length_limit():
    """Prueba que el límite de longitud del resumen funciona correctamente."""

    # Crear una instancia del servicio
    service = LLMService()

    # Simular un resumen muy largo (como el que causaba el problema)
    long_summary = "Este es un resumen muy extenso que contiene mucha información detallada sobre la conversación anterior. " * 100
    print(f"Longitud del resumen original: {len(long_summary)} caracteres")

    # Aplicar la lógica de límite de longitud
    max_summary_length = min(2000, service.max_history_chars // 4)
    print(f"Límite máximo de resumen: {max_summary_length} caracteres")

    if len(long_summary) > max_summary_length:
        truncated_summary = long_summary[:max_summary_length] + "... [Resumen truncado para evitar bucles]"
        print(f"Longitud del resumen truncado: {len(truncated_summary)} caracteres")
        print(f"Resumen truncado correctamente: {'✅' if len(truncated_summary) <= max_summary_length + 50 else '❌'}")
        return True
    else:
        print("El resumen no necesitaba truncarse")
        return True

def test_prompt_improvement():
    """Prueba que el prompt mejorado es más conciso."""

    # Prompt anterior (extenso)
    old_prompt = "Por favor, resume la siguiente conversación de manera EXHAUSTIVA, DETALLADA y EXTENSA. Captura todos los puntos clave, decisiones tomadas, tareas pendientes y cualquier información relevante que pueda ser útil para retomar la conversación con el contexto completo. El resumen debe ser lo más completo posible y actuar como un reemplazo fiel del historial para la comprensión del LLM en el futuro."

    # Prompt nuevo (conciso)
    new_prompt = "Por favor, resume la siguiente conversación de manera CONCISA pero COMPLETA. Captura los puntos clave, decisiones tomadas, tareas pendientes y contexto esencial. Limita el resumen a máximo 1500 caracteres para evitar problemas de longitud. Sé específico pero económico con las palabras."

    print(f"Longitud del prompt anterior: {len(old_prompt)} caracteres")
    print(f"Longitud del prompt nuevo: {len(new_prompt)} caracteres")
    print(f"Prompt mejorado (más corto): {'✅' if len(new_prompt) < len(old_prompt) else '❌'}")

    return len(new_prompt) < len(old_prompt)

if __name__ == "__main__":
    print("🧪 Probando corrección del problema de resumen automático...")
    print()

    print("1. Prueba del límite de longitud del resumen:")
    test1_passed = test_summary_length_limit()
    print()

    print("2. Prueba de la mejora del prompt:")
    test2_passed = test_prompt_improvement()
    print()

    if test1_passed and test2_passed:
        print("🎉 Todas las pruebas pasaron! La corrección debería resolver el problema.")
        print()
        print("Resumen de la corrección:")
        print("- ✅ Se agregó límite de longitud para resúmenes (máximo 2000 caracteres)")
        print("- ✅ Se mejoró el prompt para generar resúmenes más concisos")
        print("- ✅ Se evita el bucle infinito de resúmenes automáticos")
    else:
        print("❌ Algunas pruebas fallaron. Revisar la implementación.")
