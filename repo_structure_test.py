from repo_structure import load_repo_structure_yaml, parse_structure_rules, parse_directory_structure
import re
import pytest

TEST_CONFIG_YAML = 'test_config.yaml'


# Constant for yaml file name
TEST_CONFIG_YAML = 'test_config.yaml'

def test_successful_load_yaml():
    """Test successful loading of the yaml configuration using ruamel.yaml."""
    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    assert isinstance(config, dict)
    assert isinstance(config["structure_rules"], dict)

def test_successful_parse_structure_rules():
    """Test successful parsing of the structure rules."""
    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    rules = parse_structure_rules(config["structure_rules"])
    assert rules[0].name == "base_structure"
    assert rules[1].name == "python_package"


def test_successful_parse_directory_structure():
    """Test successful parsing of directory structure."""
    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    structure = parse_directory_structure(config["structure_rules"]["python_package"]["required"])

    assert re.compile(r"setup.py") in structure.files
    assert re.compile(r"tests/test_.*\.py") in structure.files

    assert re.compile(r"tests/") in structure.directories
    assert re.compile(r"tests/data/") in structure.directories


def test_successful_parse_directory_structure_wildcard():
    """Test successful parsing of directory structure."""
    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    structure = parse_directory_structure(config["structure_rules"]["python_package"]["optional"])

    assert re.compile(r".*/.*") in structure.files

    assert "documentation" in structure.references["docs/"]

if __name__ == '__main__':
    pytest.main(['-s', '-v', 'repo_structure_test.py'])