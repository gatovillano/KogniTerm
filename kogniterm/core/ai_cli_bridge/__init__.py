"""Capa de ejecución mínima estilo KAI-CLI para Kogniterm.

Esta subpaquete implementa un camino alternativo “fast path” que replica la
arquitectura de KAI-CLI sin reemplazar la existente:

- ToolRegistry unificado
- LLMBridge delgado sobre LiteLLM
- SuperAgent simplificado con execute_stream()

Actualmente es optativo; se deja el enganche explícito para future hooking.
"""
