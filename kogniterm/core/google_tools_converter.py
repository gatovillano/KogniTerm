import sys
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from google.generativeai.protos import FunctionDeclaration, Schema, Type

def pydantic_to_genai_type(pydantic_type: str):
    """Convierte un tipo de Pydantic a un tipo de google.generativeai.protos.Type."""
    type_map = {
        'string': Type.STRING,
        'number': Type.NUMBER,
        'integer': Type.INTEGER,
        'boolean': Type.BOOLEAN,
        'array': Type.ARRAY,
        'object': Type.OBJECT,
    }
    return type_map.get(pydantic_type, Type.STRING)

def convert_langchain_tool_to_genai(tool: BaseTool) -> FunctionDeclaration:
    """Convierte una herramienta de LangChain (BaseTool) a una FunctionDeclaration de Google AI."""
    args_schema_dict = {}
    if tool.args_schema:
        if isinstance(tool.args_schema, type) and issubclass(tool.args_schema, BaseModel):
            args_schema_dict = tool.args_schema.schema()
        elif isinstance(tool.args_schema, BaseModel):
            args_schema_dict = tool.args_schema.schema()
        elif isinstance(tool.args_schema, dict):
            args_schema_dict = tool.args_schema
        elif hasattr(tool.args_schema, 'schema'):
            args_schema_dict = tool.args_schema.schema()
    
    properties = {}
    required = args_schema_dict.get('required', [])

    for name, definition in args_schema_dict.get('properties', {}).items():
        properties[name] = Schema(
            type=pydantic_to_genai_type(definition.get('type')),
            description=definition.get('description', '')
        )

    return FunctionDeclaration(
        name=tool.name,
        description=tool.description,
        parameters=Schema(
            type=Type.OBJECT,
            properties=properties,
            required=required
        )
    )
