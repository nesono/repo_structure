"""Tests for repo_structure_schema module."""

from repo_structure.repo_structure_schema import get_json_schema


def test_get_json_schema_loads_successfully():
    """Test that the JSON schema can be loaded successfully."""
    schema = get_json_schema()

    # Verify it's a dictionary
    assert isinstance(schema, dict)

    # Verify it has the expected JSON schema metadata
    assert "$schema" in schema
    assert "$id" in schema

    # Verify it has the expected structure
    assert "$defs" in schema


def test_get_json_schema_has_directory_entry_definition():
    """Test that the schema has the directory_entry_item definition."""
    schema = get_json_schema()

    # Verify the schema has the expected definitions
    assert "directory_entry_item" in schema["$defs"]

    # Verify the directory_entry_item has expected properties
    directory_entry = schema["$defs"]["directory_entry_item"]
    assert "properties" in directory_entry
    assert "require" in directory_entry["properties"]
    assert "allow" in directory_entry["properties"]
    assert "forbid" in directory_entry["properties"]
