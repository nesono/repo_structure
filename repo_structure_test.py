# pylint: disable=import-error
"""Tests for repo_structure library functions."""
import pprint
import re

import pytest
from repo_structure import (
    StructureRule,
    load_repo_structure_yaml,
    load_repo_structure_yamls,
    parse_directory_structure,
    parse_structure_rules,
    parse_directory_mappings,
)


TEST_CONFIG_YAML = "test_config.yaml"


def test_successful_load_yaml():
    """Test successful loading of the yaml configuration using ruamel.yaml."""
    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    assert isinstance(config, dict)
    assert isinstance(config["structure_rules"], dict)


def test_successful_load_yamls():
    """Test loading from string."""
    config = load_repo_structure_yamls("")
    assert config is None

    test_yaml = r"""
base_structure:
    files:
        - "LICENSE": required
        - "README.md": required
        - '.*\.md': optional
directory_mappings:
    /:
        - use_rule: base_structure
"""
    config = load_repo_structure_yamls(test_yaml)
    assert isinstance(config, dict)
    assert isinstance(config, dict)


def test_successful_parse_structure_rules():
    """Test successful parsing of the structure rules."""
    rules = parse_structure_rules({})
    assert len(rules) == 0

    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    rules = parse_structure_rules(config["structure_rules"])

    assert "base_structure" in rules
    assert "python_package" in rules

    assert re.compile(r"setup.py") in rules["python_package"].required.files
    assert re.compile(r"test/data") in rules["python_package"].required.directories

    assert (
        "python_package" in rules["python_package"].optional.use_rule[re.compile(".*")]
    )
    assert (
        "documentation" in rules["python_package"].optional.use_rule[re.compile("docs")]
    )

    assert re.compile(r"src/.*\.py") in rules["python_package"].dependencies
    assert (
        re.compile(r"../test/test_.*\.py")
        == rules["python_package"].dependencies[re.compile(r"src/.*\.py")].depends
    )


def test_fail_parse_structure_rules_dangling_use_rule():
    """Test failing parsing of the structure rules with dangling use_rule."""
    test_yaml = r"""
    python_package:
      dirs:
        - name: "docs"
          mode: optional
          use_rule: documentation
    """
    config = load_repo_structure_yamls(test_yaml)
    with pytest.raises(ValueError):
        parse_structure_rules(config)


def test_successful_parse_directory_structure():
    """Test successful parsing of directory structure."""
    structure = StructureRule()
    parse_directory_structure({}, structure)
    assert len(structure.name) == 0
    assert len(structure.dependencies) == 0

    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    parse_directory_structure(config["structure_rules"]["python_package"], structure)

    assert re.compile(r"setup.py") in structure.required.files
    assert re.compile(r"test/test_.*\.py") in structure.required.files

    assert re.compile(r"test") in structure.required.directories
    assert re.compile(r"test/data") in structure.required.directories


def test_successful_parse_directory_structure_wildcard():
    """Test successful parsing of directory structure."""
    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    structure = StructureRule()
    parse_directory_structure(config["structure_rules"]["python_package"], structure)
    assert re.compile(r".*") in structure.optional.directories


def test_fail_directory_structure_mixing_use_rule_and_files():
    """Test failing parsing of directory when use_rule and files are mixed."""
    test_config = """
package:
    dirs:
        - name: "docs"
          mode: optional
          use_rule: documentation
          dirs:
            - ".*/": optional
              files:
                - ".*": optional
documentation:
    files:
        - name: "README.md"
"""
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        structure = parse_structure_rules(config)
        pprint.pprint(structure)


def test_fail_parse_file_dependencies_missing_base():
    """Test failing parsing of file dependencies using bad key."""
    test_config = r"""
files:
    - name: "README.md"
      depends_path: 'test_.*\.py'
    """
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        structure = StructureRule()
        parse_directory_structure(config, structure)
        pprint.pprint(structure)


def test_fail_parse_bad_key():
    """Test failing parsing of file dependencies using bad key."""
    test_config = r"""
files:
    - name: "README.md"
      foo: '.*\.py'
    """
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        structure = StructureRule()
        parse_directory_structure(config, structure)
        pprint.pprint(structure)

def test_successful_parse_directory_mappings():
    """"Test successful parsing of directory mappings."""
    mappings = parse_directory_mappings({})
    assert len(mappings.map) == 0

    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    mappings = parse_directory_mappings(config["directory_mappings"])
    assert len(mappings.map) == 2
    assert re.compile(r"/") in mappings.map
    assert re.compile(r"/docs/") in mappings.map
    assert mappings.map[re.compile(r"/")] == "python_package"
    assert mappings.map[re.compile(r"/docs/")] == "documentation"

def test_fail_directory_mappings_bad_key():
    test_config = """
/:
    - use_rule: python_package
/docs/:
    - foo: documentation
    """
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        mappings = parse_directory_mappings(config)
        pprint.pprint(mappings)

def test_fail_directory_mappings_bad_list():
    test_config = """
/:
    - use_rule: python_package
    - foo: documentation
    """
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        mappings = parse_directory_mappings(config)
        pprint.pprint(mappings)

if __name__ == "__main__":
    pytest.main(["-s", "-v", __file__])
