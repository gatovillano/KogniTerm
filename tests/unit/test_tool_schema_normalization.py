from kogniterm.core.utils.tool_utils import normalize_tool_parameters_schema


def test_normalize_tool_parameters_schema_adds_items_type_for_arrays():
    schema = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "description": "Rutas a leer",
            }
        },
        "required": ["paths"],
    }

    normalized = normalize_tool_parameters_schema(schema)

    assert normalized["properties"]["paths"]["type"] == "array"
    assert normalized["properties"]["paths"]["items"] == {"type": "string"}


def test_normalize_tool_parameters_schema_keeps_existing_array_item_type():
    schema = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
            }
        },
    }

    normalized = normalize_tool_parameters_schema(schema)

    assert normalized["properties"]["paths"]["items"]["type"] == "string"
