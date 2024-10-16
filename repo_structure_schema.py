"""JSON Schema for YAML validation."""

yaml_schema = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "structure_rules": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "p": {"type": "string"},
                            "required": {"type": "boolean"},
                            "if_exists": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "p": {"type": "string"},
                                        "required": {"type": "boolean"}
                                    },
                                    "required": ["p"]
                                }
                            },
                            "use_rule": {"type": "string"}
                        },
                        "required": ["p"]
                    }
                }
            }
        },
        "templates": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "p": {"type": "string"},
                            "required": {"type": "boolean"}
                        },
                        "required": ["p"]
                    }
                }
            }
        },
        "directory_map": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "use_rule": {"type": "string"},
                            "use_template": {"type": "string"},
                            "component_name": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "anyOf": [
                            {"required": ["use_rule"]},
                            {"required": ["use_template"]}
                        ]
                    }
                }
            }
        }
    },
    "required": ["structure_rules", "templates", "directory_map"]
}

