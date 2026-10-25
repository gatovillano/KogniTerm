from kogniterm.core.antigravity_client import AntigravityClient
from kogniterm.core.utils.tool_utils import normalize_tool_parameters_schema

def test_antigravity_client_map_tools_converts_numeric_enums():
    tools = [{
        "type": "function",
        "function": {
            "name": "set_disappearing_messages",
            "description": "Sets message expiration timer",
            "parameters": {
                "type": "object",
                "properties": {
                    "timer": {
                        "type": "integer",
                        "enum": [86400, 604800, 2592000]
                    }
                }
            }
        }
    }]
    mapped = AntigravityClient.map_tools(tools)
    assert mapped is not None
    decl = mapped[0]["functionDeclarations"][0]
    timer_prop = decl["parameters"]["properties"]["timer"]
    assert timer_prop["enum"] == ["86400", "604800", "2592000"]
    assert timer_prop["type"] == "INTEGER"

def test_normalize_tool_parameters_schema_converts_numeric_enums():
    schema = {
        "type": "object",
        "properties": {
            "ttl": {
                "type": "integer",
                "enum": [86400, 604800, 2592000]
            },
            "category": {
                "enum": [1, 2, 3]
            }
        }
    }
    normalized = normalize_tool_parameters_schema(schema)
    assert normalized["properties"]["ttl"]["enum"] == ["86400", "604800", "2592000"]
    assert normalized["properties"]["category"]["enum"] == ["1", "2", "3"]
    assert normalized["properties"]["category"]["type"] == "string"
