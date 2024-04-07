# pylint: disable=import-error
"""Tests for repo_structure library functions."""

import re

import pytest
from repo_structure import (
    load_repo_structure_yaml,
    load_repo_structure_yamls,
    parse_directory_structure,
    parse_file_dependencies,
    parse_includes,
    parse_structure_rules,
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
  required:
    - "LICENSE"
    - "README.md"
  optional:
    - '.*\.md'
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
    assert re.compile(r"tests/data/") in rules["python_package"].required.directories

    assert (
        "python_package" in rules["python_package"].optional.use_rule[re.compile(".*/")]
    )
    assert (
        "documentation"
        in rules["python_package"].optional.use_rule[re.compile("docs/")]
    )

    assert "base_structure" in rules["python_package"].includes

    assert "implementation_and_test" in rules["python_package"].file_dependencies
    assert (
        re.compile(r"test_.*\.py")
        == rules["python_package"]
        .file_dependencies["implementation_and_test"]
        .dependent
    )


def test_fail_parse_structure_rules_dangling_include():
    """Test failing parsing of the structure rules with dangling includes."""
    test_yaml = r"""
python_package:
  includes:
    - dangling_structure
"""
    config = load_repo_structure_yamls(test_yaml)
    with pytest.raises(ValueError):
        parse_structure_rules(config)


def test_fail_parse_structure_rules_dangling_use_rule():
    """Test failing parsing of the structure rules with dangling use_rule."""
    test_yaml = r"""
    python_package:
      optional:
        - "docs/":
            - use_rule: documentation
    """
    config = load_repo_structure_yamls(test_yaml)
    with pytest.raises(ValueError):
        parse_structure_rules(config)


def test_successful_parse_directory_structure():
    """Test successful parsing of directory structure."""
    structure = parse_directory_structure({})
    assert len(structure.directories) == 0
    assert len(structure.files) == 0
    assert len(structure.use_rule) == 0

    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    structure = parse_directory_structure(
        config["structure_rules"]["python_package"]["required"]
    )

    assert re.compile(r"setup.py") in structure.files
    assert re.compile(r"tests/test_.*\.py") in structure.files

    assert re.compile(r"tests/") in structure.directories
    assert re.compile(r"tests/data/") in structure.directories


def test_successful_parse_directory_structure_wildcard():
    """Test successful parsing of directory structure."""
    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    structure = parse_directory_structure(
        config["structure_rules"]["python_package"]["optional"]
    )
    assert "python_package" in structure.use_rule[re.compile(".*/")]


def test_fail_directory_structure_mixing_use_rule_and_files():
    """Test failing parsing of directory when use_stucture and files are mixed."""
    test_config = """
- "docs/":
    - use_rule: documentation
    - ".*/":
        - ".*"
"""
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        parse_directory_structure(config)


def test_fail_directory_structure_double_use_rule():
    """Test failing parsing of dirctory_structure when use_rule is used more than once."""
    test_config = """
- "docs/":
  - use_rule: documentation
  - use_rule: python_package
"""
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        print(parse_directory_structure(config))


def test_fail_directory_structure_missing_trailing_slash():
    """Test failing parsing of dirctory_structure when use_rule is used more than once."""
    test_config = """
- "docs":
  - use_rule: documentation
  - use_rule: python_package
"""
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        print(parse_directory_structure(config))


def test_successful_parse_includes():
    """Test successful parsing of includes."""
    includes = parse_includes([])
    assert len(includes) == 0

    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    includes = parse_includes(config["structure_rules"]["python_package"]["includes"])
    assert "base_structure" in includes


def test_fail_parse_includes_no_list():
    """Test successful parsing of includes."""
    with pytest.raises(TypeError):
        parse_includes({})


def test_successful_parse_file_dependencies():
    """Test successful parsing of file dependencies."""
    dependencies = parse_file_dependencies({})
    assert len(dependencies) == 0

    config = load_repo_structure_yaml(TEST_CONFIG_YAML)
    dependencies = parse_file_dependencies(
        config["structure_rules"]["python_package"]["file_dependencies"]
    )
    assert "implementation_and_test" in dependencies
    assert "techspec_and_requirements" in dependencies


def test_fail_parse_file_dependencies_too_many_entries():
    """ "Test failing parsing of file dependencies using multiple base spec."""
    test_config = r"""
- implementation_and_test:
    base: '.*\.py'
    bad_entry: '.*\.py'
    dependent: 'test_.*\.py'
    """
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        parse_file_dependencies(config)


def test_fail_parse_file_dependencies_missing_base():
    """ "Test failing parsing of file dependencies using multiple base spec."""
    test_config = r"""
- implementation_and_test:
    bad_entry: '.*\.py'
    dependent: 'test_.*\.py'
    """
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        parse_file_dependencies(config)


def test_fail_parse_file_dependencies_missing_dependent():
    """ "Test failing parsing of file dependencies using multiple base spec."""
    test_config = r"""
- implementation_and_test:
    base: '.*\.py'
    bad_entry: '.*\.py'
    """
    config = load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        parse_file_dependencies(config)


if __name__ == "__main__":
    pytest.main(["-s", "-v", "repo_structure_test.py"])
