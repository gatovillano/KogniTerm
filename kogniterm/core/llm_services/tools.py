"""
Herramientas del sistema y utilidades de definición.
"""
from typing import Any, Dict, List

from kogniterm.core.llm_services.types import ToolDefinition


# Herramientas del sistema
SYSTEM_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "sequential_thinking",
        "description": "Planifica y ejecuta tareas complejas paso a paso, manteniendo contexto y estado.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "La tarea principal a resolver",
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Pasos opcionales a seguir",
                },
                "context": {
                    "type": "string",
                    "description": "Contexto adicional relevante",
                },
            },
            "required": ["task"],
        },
    },
    {
        "name": "mental_model",
        "description": "Aplica modelos mentales para analizar problemas desde diferentes perspectivas.",
        "parameters": {
            "type": "object",
            "properties": {
                "model_name": {
                    "type": "string",
                    "enum": [
                        "first_principles",
                        "opportunity_cost",
                        "error_propagation",
                        "rubber_duck",
                        "pareto_principle",
                        "occams_razor",
                    ],
                    "description": "Nombre del modelo mental a aplicar",
                },
                "problem": {
                    "type": "string",
                    "description": "El problema a analizar",
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Pasos a seguir en el análisis",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Razonamiento desarrollado",
                },
                "conclusion": {
                    "type": "string",
                    "description": "Conclusiones del análisis",
                },
            },
            "required": ["model_name", "problem"],
        },
    },
    {
        "name": "debugging_approach",
        "description": "Aplica enfoques sistemáticos de depuración para identificar y resolver problemas.",
        "parameters": {
            "type": "object",
            "properties": {
                "approach_name": {
                    "type": "string",
                    "enum": [
                        "binary_search",
                        "reverse_engineering",
                        "divide_conquer",
                        "backtracking",
                        "cause_elimination",
                        "program_slicing",
                    ],
                    "description": "Enfoque de depuración a utilizar",
                },
                "issue": {
                    "type": "string",
                    "description": "Descripción del problema a depurar",
                },
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Pasos de depuración",
                },
                "findings": {
                    "type": "string",
                    "description": "Hallazgos encontrados",
                },
                "resolution": {
                    "type": "string",
                    "description": "Cómo se resolvió el problema",
                },
            },
            "required": ["approach_name", "issue"],
        },
    },
    {
        "name": "creative_thinking",
        "description": "Genera ideas creativas y soluciones innovadoras usando diversos enfoques.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "El problema o reto creativo",
                },
                "ideas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ideas generadas",
                },
                "techniques": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Técnicas creativas utilizadas",
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "visual_reasoning",
        "description": "Procesa información visual, diagramas y modelos espaciales.",
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["create", "transform", "observe"],
                    "description": "Operación visual a realizar",
                },
                "diagram_type": {
                    "type": "string",
                    "enum": [
                        "flowchart",
                        "state_diagram",
                        "concept_map",
                        "tree_diagram",
                        "block_diagram",
                    ],
                    "description": "Tipo de diagrama",
                },
                "iteration": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Número de iteración",
                },
                "observation": {
                    "type": "string",
                    "description": "Observaciones",
                },
                "insight": {
                    "type": "string",
                    "description": "Insights obtenidos",
                },
                "hypothesis": {
                    "type": "string",
                    "description": "Hipótesis formuladas",
                },
                "next_operation_needed": {
                    "type": "boolean",
                    "description": "Si se necesita otra operación",
                },
            },
            "required": ["operation", "diagram_type", "iteration"],
        },
    },
    {
        "name": "metacognitive_monitoring",
        "description": "Monitorea y evalúa el propio proceso de pensamiento y conocimiento.",
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Tarea a monitorear",
                },
                "stage": {
                    "type": "string",
                    "enum": [
                        "planning",
                        "executing",
                        "monitoring",
                        "evaluating",
                        "reflecting",
                    ],
                    "description": "Etapa actual",
                },
                "overall_confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confianza general (0-1)",
                },
                "uncertainty_areas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Áreas de incertidumbre",
                },
                "recommended_approach": {
                    "type": "string",
                    "description": "Enfoque recomendado",
                },
            },
            "required": ["task", "stage", "overall_confidence"],
        },
    },
    {
        "name": "scientific_method",
        "description": "Aplica el método científico para formular y probar hipótesis.",
        "parameters": {
            "type": "object",
            "properties": {
                "stage": {
                    "type": "string",
                    "enum": [
                        "observation",
                        "question",
                        "hypothesis",
                        "experiment",
                        "analysis",
                        "conclusion",
                        "iteration",
                    ],
                    "description": "Etapa actual del método científico",
                },
                "observation": {
                    "type": "string",
                    "description": "Observación inicial",
                },
                "question": {
                    "type": "string",
                    "description": "Pregunta de investigación",
                },
                "hypothesis": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string"},
                        "variables": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "type": {"type": "string", "enum": ["independent", "dependent", "controlled", "confounding"]},
                                    "operationalization": {"type": "string"},
                                },
                            },
                        },
                        "assumptions": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "hypothesis_id": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "domain": {"type": "string"},
                        "iteration": {"type": "number", "minimum": 0},
                        "alternative_to": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "refinement_of": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["proposed", "testing", "supported", "refuted", "refined"],
                        },
                    },
                    "description": "Hipótesis",
                },
                "experiment": {
                    "type": "object",
                    "properties": {
                        "design": {"type": "string"},
                        "methodology": {"type": "string"},
                        "predictions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "if": {"type": "string"},
                                    "then": {"type": "string"},
                                    "else": {"type": "string"},
                                },
                            },
                        },
                        "experiment_id": {"type": "string"},
                        "hypothesis_id": {"type": "string"},
                        "control_measures": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "description": "Diseño experimental",
                },
            },
            "required": ["stage"],
        },
    },
    {
        "name": "structured_argumentation",
        "description": "Construye y evalúa argumentaciones estructuradas.",
        "parameters": {
            "type": "object",
            "properties": {
                "claim": {
                    "type": "string",
                    "description": "Afirmación principal",
                },
                "premises": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Premisas que soportan la afirmación",
                },
                "conclusion": {
                    "type": "string",
                    "description": "Conclusión",
                },
                "argument_type": {
                    "type": "string",
                    "enum": ["deductive", "inductive", "abductive", "analogical"],
                    "description": "Tipo de argumentación",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Confianza en la argumentación (0-1)",
                },
                "next_argument_needed": {
                    "type": "boolean",
                    "description": "Si se necesita otro argumento",
                },
            },
            "required": ["claim", "premises", "conclusion", "argument_type", "confidence"],
        },
    },
    {
        "name": "visualDashboard",
        "description": "Genera un dashboard visual interactivo con métricas y estado.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Título del dashboard",
                },
                "widgets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["chart", "metric", "table", "status"]},
                            "title": {"type": "string"},
                            "data": {"type": "object"},
                        },
                    },
                    "description": "Widgets del dashboard",
                },
                "refresh_interval": {
                    "type": "number",
                    "minimum": 0,
                    "description": "Intervalo de actualización en segundos",
                },
            },
            "required": ["title", "widgets"],
        },
    },
]


def get_system_tool_definitions() -> List[ToolDefinition]:
    """
    Convierte SYSTEM_TOOLS a objetos ToolDefinition.
    """
    return [
        ToolDefinition(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
            strict=False,
            metadata={"system": True},
        )
        for tool in SYSTEM_TOOLS
    ]


def find_tool_definition(name: str) -> ToolDefinition:
    """
    Busca una definición de herramienta por nombre.
    """
    for tool_def in get_system_tool_definitions():
        if tool_def.name == name:
            return tool_def
    raise ValueError(f"Herramienta no encontrada: {name}")
