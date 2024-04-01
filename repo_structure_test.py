from repo_structure import load_repo_structure_yaml, parse_structure_rules, parse_directory_structure, parse_file_dependencies
import re
import pytest

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

    assert "base_structure" in rules
    assert "python_package" in rules

    assert re.compile(r"setup.py") in rules["python_package"].required.files
    assert re.compile(r"tests/data/") in rules["python_package"].required.directories

    assert re.compile(r".*/.*") in rules["python_package"].optional.files
    assert "documentation" in rules["python_package"].optional.use_structure["docs/"]

    assert "base_structure" in rules["python_package"].includes

    assert "implementation_and_test" in rules["python_package"].file_dependencies
    assert re.compile(r"test_.*\.py") == rules["python_package"].file_dependencies["implementation_and_test"].dependent


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
    assert "documentation" in structure.use_structure["docs/"]

def test_parse_successful_file_dependencies():
    """Test successful parsing of file dependencies."""
    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    dependencies = parse_file_dependencies(config["structure_rules"]["python_package"]["file_dependencies"])
    assert "implementation_and_test" in dependencies
    assert "techspec_and_requirements" in dependencies


if __name__ == '__main__':
    pytest.main(['-s', '-v', 'repo_structure_test.py'])