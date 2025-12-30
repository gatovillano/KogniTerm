from crewai import Agent
from typing import List, Any

class ReporterAgent:
    """Agente encargado de transformar datos estructurados en informes Markdown."""

    def __init__(self, llm):
        self.llm = llm

    def markdown_reporter(self) -> Agent:
        """Crea un agente experto en redacción técnica y documentación."""
        return Agent(
            role='Redactor de Informes Técnicos',
            goal='Generar un informe en Markdown profesional, claro y detallado a partir de un objeto JSON.',
            backstory="""Eres un documentalista técnico de primer nivel. Tu especialidad es tomar 
            datos complejos y estructurados para presentarlos de una manera que sea fácil de digerir 
            para desarrolladores y stakeholders. Te aseguras de que el Markdown sea impecable, 
            con tablas, bloques de código bien resaltados y una jerarquía de encabezados lógica.""",
            tools=[], # Este agente procesa la salida del sintetizador
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
