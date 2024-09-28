# pylint: disable=import-error
"""Tests for repo_structure library functions."""
import sys

import pytest
from repo_structure_config import (
    Configuration,
    UseRuleError,
    ConfigurationParseError,
    DirectoryStructureError,
)


def test_successful_parse():
    """Test successful parsing with many features."""
    test_yaml = r"""
structure_rules:
  basic_rule:
    files:
      - name: "README.md"
        mode: required
        # mode: required is default
      - name: '.*\.md'
        mode: optional
    dirs:
      - name: '.github'
        files:
          - name: '[^/]*'
  recursive_rule:
    files:
      - name: '[^/]*\.py'
        mode: required
    dirs:
      - name: "package"
        mode: optional
        use_rule: recursive_rule
  template_rule_second_map:
    files:
      - name: "BUILD"
    dirs:
      - name: "example"
        dirs:
          - name: "doc"
            mode: required
        files:
          - name: "[^/]*"

directory_map:
  /:
    - use_rule: basic_rule
    - use_rule: recursive_rule
  /test_folder_structure/:
    - use_rule: template_rule_second_map
    """
    # parsing should not throw using the above yaml
    config = Configuration(test_yaml, True)

    # assert on basics
    assert config is not None
    assert config.directory_map is not None
    assert config.structure_rules is not None


def test_fail_parse_dangling_use_rule_in_directory_map():
    """Test failing parsing of the structure rules with dangling use_rule."""
    test_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: "README.md"

directory_map:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    with pytest.raises(UseRuleError):
        Configuration(test_yaml, True)


def test_fail_parse_dangling_use_rule_in_structure_rule():
    """Test failing parsing of the structure rules with dangling use_rule."""
    test_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: "README.md"
    dirs:
      - name: 'docs'
        use_rule: python_package

directory_map:
  /:
    - use_rule: base_structure
    """
    with pytest.raises(UseRuleError):
        Configuration(test_yaml, True)


def test_fail_directory_structure_mixing_use_rule_and_files():
    """Test failing parsing of directory when use_rule and files are mixed."""
    test_config = r"""
structure_rules:
    package:
        dirs:
            - name: "docs"
              mode: optional
              use_rule: documentation
              dirs:
                - ".*/": optional
                  files:
                    - ".*": optional
directory_map:
/:
    - use_rule: package
"""
    with pytest.raises(UseRuleError):
        Configuration(test_config, True)


def test_fail_parse_bad_key_in_structure_rule():
    """Test failing parsing of file dependencies using bad key."""
    test_config = r"""
structure_rules:
    bad_key_rule:
        files:
            - name: "README.md"
              foo: '.*\.py'
directory_map:
/:
    - use_rule: bad_key_rule
    """
    with pytest.raises(ValueError):
        Configuration(test_config, True)


def test_fail_directory_map_key_in_directory_map():
    """Test failing parsing of file mappings using bad key."""
    test_config = """
structure_rules:
    correct_rule:
        files:
            - name: 'unused_file'
              mode: optional
directory_map:
    /:
        - use_rule: correct_rule
        - foo: documentation
    """
    with pytest.raises(ValueError):
        Configuration(test_config, True)


def test_fail_use_rule_not_recursive():
    """Test use rule usage not recursive."""
    config_yaml = r"""
structure_rules:
    license_rule:
        files:
            - name: LICENSE
    bad_use_rule:
        dirs:
            - name: '.*'
              mode: required
              use_rule: license_rule
directory_map:
  /:
    - use_rule: bad_use_rule
    """
    with pytest.raises(UseRuleError):
        Configuration(config_yaml, True)


def test_fail_directory_map_missing_trailing_slash():
    """Test missing trailing slash in directory_map entry."""
    config_yaml = r"""
structure_rules:
    license_rule:
        files:
            - name: LICENSE
directory_map:
  /:
    - use_rule: license_rule
  /missing_trailing_slash:
    - use_rule: license_rule
    """
    with pytest.raises(DirectoryStructureError):
        Configuration(config_yaml, True)


def test_fail_directory_map_missing_starting_slash():
    """Test missing starting slash in directory_map entry."""
    config_yaml = r"""
structure_rules:
    license_rule:
        files:
            - name: LICENSE
directory_map:
  /:
    - use_rule: license_rule
  missing_starting_slash/:
    - use_rule: license_rule
    """
    with pytest.raises(DirectoryStructureError):
        Configuration(config_yaml, True)


def test_fail_config_file_structure_rule_conflict():
    """Test conflicting rules for automatic config file addition.

    This test requires file parsing, since the parsed file name will
    be added as an automatic rule.
    """
    with pytest.raises(ConfigurationParseError):
        Configuration("conflicting_test_config.yaml")


if __name__ == "__main__":
    sys.exit(pytest.main(["-s", "-v", __file__]))
