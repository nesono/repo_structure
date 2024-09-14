# pylint: disable=import-error
"""Tests for repo_structure library functions."""
import pprint
import re
import sys

import pytest
from repo_structure_config import (
    Configuration,
    ContentRequirement,
    DirectoryEntryWrapper,
    EntryType,
    StructureRule,
    UseRuleError,
    _load_repo_structure_yaml,
    _load_repo_structure_yamls,
    _parse_directory_mappings,
    _parse_directory_structure,
    _parse_structure_rules,
    ConfigurationParseError,
)


TEST_CONFIG_YAML = "repo_structure_config.yaml"


def test_successful_load_yaml():
    """Test successful loading of the yaml configuration using ruamel.yaml."""
    config = _load_repo_structure_yaml(TEST_CONFIG_YAML)
    assert isinstance(config, dict)
    assert isinstance(config["structure_rules"], dict)


def test_successful_load_yamls():
    """Test loading from string."""
    config = _load_repo_structure_yamls("")
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
    config = _load_repo_structure_yamls(test_yaml)
    assert isinstance(config, dict)
    assert isinstance(config, dict)


def test_successful_parse_structure_rules():
    """Test successful parsing of the structure rules."""
    rules = _parse_structure_rules({})
    assert len(rules) == 0

    config = _load_repo_structure_yaml(TEST_CONFIG_YAML)
    rules = _parse_structure_rules(config["structure_rules"])

    assert "base_structure" in rules
    assert "python_package" in rules

    assert (
        DirectoryEntryWrapper(
            path=re.compile(r"[^/]*\.py"),
            entry_type=EntryType.FILE,
            content_requirement=ContentRequirement.OPTIONAL,
        )
        in rules["python_package"].entries
    )

    assert (
        DirectoryEntryWrapper(
            path=re.compile(r"[^/]*"),
            entry_type=EntryType.DIR,
            content_requirement=ContentRequirement.OPTIONAL,
            use_rule="python_package",
        )
        in rules["python_package"].entries
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
    config = _load_repo_structure_yamls(test_yaml)
    with pytest.raises(UseRuleError):
        _parse_structure_rules(config)


def test_successful_parse_directory_structure():
    """Test successful parsing of directory structure."""
    structure = StructureRule()
    _parse_directory_structure({}, structure)
    assert len(structure.name) == 0
    assert len(structure.dependencies) == 0

    config = _load_repo_structure_yaml(TEST_CONFIG_YAML)
    structure.name = "python_package"
    _parse_directory_structure(config["structure_rules"]["python_package"], structure)

    assert (
        DirectoryEntryWrapper(
            path=re.compile(r"[^/]*\.py"),
            entry_type=EntryType.FILE,
            content_requirement=ContentRequirement.OPTIONAL,
        )
        in structure.entries
    )


def test_successful_parse_directory_structure_wildcard():
    """Test successful parsing of directory structure."""
    config = _load_repo_structure_yaml(TEST_CONFIG_YAML)
    structure = StructureRule()
    structure.name = "python_package"
    _parse_directory_structure(config["structure_rules"]["python_package"], structure)
    assert (
        DirectoryEntryWrapper(
            path=re.compile(r"[^/]*"),
            entry_type=EntryType.DIR,
            content_requirement=ContentRequirement.OPTIONAL,
            use_rule="python_package",
        )
        in structure.entries
    )


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
    config = _load_repo_structure_yamls(test_config)
    with pytest.raises(UseRuleError):
        structure = _parse_structure_rules(config)
        pprint.pprint(structure)


def test_fail_parse_bad_key():
    """Test failing parsing of file dependencies using bad key."""
    test_config = r"""
files:
    - name: "README.md"
      foo: '.*\.py'
    """
    config = _load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        structure = StructureRule()
        _parse_directory_structure(config, structure)
        pprint.pprint(structure)


def test_successful_parse_directory_mappings():
    """Test successful parsing of directory mappings."""
    mappings = _parse_directory_mappings({})
    assert len(mappings) == 0

    config = _load_repo_structure_yaml(TEST_CONFIG_YAML)
    mappings = _parse_directory_mappings(config["directory_mappings"])
    assert len(mappings) == 2
    assert "/" in mappings
    assert "/doc/" in mappings
    assert mappings["/"] == ["base_structure", "python_package"]
    assert mappings["/doc/"] == ["documentation"]


def test_fail_directory_mappings_bad_key():
    """Test failing parsing of file mappings using bad key."""
    test_config = """
/:
    - use_rule: python_package
/docs/:
    - foo: documentation
    """
    config = _load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        mappings = _parse_directory_mappings(config)
        pprint.pprint(mappings)


def test_fail_directory_mappings_bad_list():
    """Test failing parsing of file mappings using multiple entries."""
    test_config = """
/:
    - use_rule: python_package
    - foo: documentation
    """
    config = _load_repo_structure_yamls(test_config)
    with pytest.raises(ValueError):
        mappings = _parse_directory_mappings(config)
        pprint.pprint(mappings)


def test_successful_full_example_parse():
    """Test parsing of the full example file."""
    config = Configuration(TEST_CONFIG_YAML)
    assert config is not None
    assert config.directory_mappings is not None
    assert "/doc/" in config.directory_mappings
    assert "/" in config.directory_mappings
    assert config.structure_rules is not None
    assert "base_structure" in config.structure_rules
    assert "python_package" in config.structure_rules
    assert "documentation" in config.structure_rules


def test_fail_use_rule_not_recursive():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: LICENSE
  python_package:
    dirs:
      - name: '.*'
        mode: required
        use_rule: base_structure
directory_mappings:
  /:
    - use_rule: python_package
    """
    with pytest.raises(UseRuleError):
        Configuration(config_yaml, True)

def test_fail_config_file_structure_rule_conflict():

    with pytest.raises(ConfigurationParseError):
        Configuration("conflicting_test_config.yaml")


if __name__ == "__main__":
    sys.exit(pytest.main(["-s", "-v", __file__]))
