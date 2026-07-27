"""JSON Schema for YAML validation."""

import json
from pathlib import Path


def get_json_schema() -> dict:
    """Get the JSON schema for YAML validation."""
    current_dir = Path(__file__).parent
    json_schema_file = current_dir / "config.schema.json"

    with json_schema_file.open() as file:
        yaml_schema = json.load(file)

    return yaml_schema
