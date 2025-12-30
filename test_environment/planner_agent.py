#!/usr/bin/env python3
"""
Agente Planificador para el ResearcherAgent refactorizado.
Este agente decide qué agentes investigadores son necesarios para una consulta.
"""

from typing import List, Dict, Any
from crewai import Agent
from langchain_openai import OpenAI


class PlannerAgent:
    """Agente encargado de planificar la investigación."""

    def __init__(self, llm: OpenAI):
        self.llm = llm
        self.agents: List[Agent] = []

    def create_agent(self, role: str, goal: str, backstory: str, tools: List[Any]) -> Agent:
        """Crea un agente con una función específica."""
        return Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            tools=tools,
            llm=self.llm,
            verbose=True
        )

    def plan_research(self, query: str) -> Dict[str, List[str]]:
        """
        Analiza la consulta y decide qué agentes investigadores son necesarios.
        
        Args:
            query: La consulta del usuario.
        
        Returns:
            Un diccionario con los agentes seleccionados y sus tareas.
        """
        # Lógica para decidir qué agentes son necesarios
        # Por ahora, seleccionamos todos los agentes para pruebas
        selected_agents = {
            "Internet": ["Buscar información en la web"],
            "GitHub": ["Investigar repositorios en GitHub"],
            "Código Base": ["Analizar el código local"],
            "Análisis de Código": ["Realizar análisis estático"]
        }
        
        return selected_agents