"""JSON Schema for YAML validation."""

yaml_schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/nesono/repo_structure.git/config.schema.json",
    "$defs": {
        "directory_entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "p": {"type": "string"},
                    "required": {"type": "boolean"},
                    "if_exists": {"ref": "#/$defs/directory_entries"},
                    "use_rule": {"type": "string"},
                },
                "additionalProperties": False,
                "required": ["p"],
            },
        },
        "directory_map": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "use_rule": {"type": "string"},
                    "use_template": {"type": "string"},
                    "parameters": {
                        "type": "object",
                        "properties": {
                            ".*": {
                                "type": "array",
                            }
                        },
                    },
                },
                "additionalProperties": False,
                "anyOf": [
                    {"required": ["use_rule"]},
                    {"required": ["use_template", "parameters"]},
                ],
            },
        },
    },
    "title": "Repo Structure Configuration JSON Schema",
    "type": "object",
    "properties": {
        "structure_rules": {
            "description": """Contains named structure rules specifying allowed and required
                              directory entries and are mapped to directories through the
                              directory_map""",
            "type": "object",
            "patternProperties": {
                ".*": {"$ref": "#/$defs/directory_entries"},
            },
        },
        "templates": {
            "description": """Contains named templates that are expanded by usage in the
                              directory_map into structure rules""",
            "type": "object",
            "patternProperties": {
                ".*": {"$ref": "#/$defs/directory_entries"},
            },
        },
        "directory_map": {
            "type": "object",
            "patternProperties": {
                ".*": {"$ref": "#/$defs/directory_map"},
            },
        },
    },
    "required": ["directory_map"],
    "anyOf": [
        {"required": ["structure_rules"]},
        {"required": ["templates"]},
    ],
}
