# pylint: disable=import-error
"""Tests for repo_structure library functions."""
import sys

import pytest
from repo_structure_config import (
    Configuration,
    UseRuleError,
    ConfigurationParseError,
    DirectoryStructureError,
    StructureRuleError,
)


def test_successful_parse():
    """Test successful parsing with many features.

    This is not so much a test than a showroom.
    """
    test_yaml = r"""
structure_rules:
  basic_rule:
    - 'README.md': required
      # mode: required is default
    - '[^/]*\.md': optional
    - '.github/': optional
      if_exists:
      - 'CODEOWNERS'
  recursive_rule:
    - '[^/]*\.py'
    - 'package/[^/]*':
      use_rule: recursive_rule
  template_rule_second_map:
    - "BUILD"
    - "example/[^/]*"
    - "example/doc/"
templates:
  software_component:
    - '{{component_name}}_component.cpp'
    - '{{component_name}}_component.h'
    - '{{component_name}}_config.h': optional
    - '{{component_name}}_factory.cpp'
    - '{{component_name}}_factory.h'
    - 'BUILD'
    - 'README.md'
    - 'doc/{{component_name}}.swreq.md'
    - 'doc/{{component_name}}.techspec.md'
    - '[^/]*\_test.cpp': optional
    - 'tests/[^/]*_test.cpp': optional
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
    - "README.md"

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
    - 'README.md'
    # if we use a use_rule, we need to add required/optional, too
    - 'docs/': required
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
      - "docs/": optional
        use_rule: documentation
      - "docs/[^/]*/": optional
      - "docs/[^/]/[^/]*": optional
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
      - "README.md": optional
        bad_key: '.*\.py'
directory_map:
/:
    - use_rule: bad_key_rule
    """
    with pytest.raises(StructureRuleError):
        Configuration(test_config, True)


def test_fail_directory_map_key_in_directory_map():
    """Test failing parsing of file mappings using bad key."""
    test_config = """
structure_rules:
    correct_rule:
        - 'unused_file'
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
        - LICENSE
    bad_use_rule:
        - '.*/': optional
          use_rule: license_rule
directory_map:
  /:
    # it doesn't matter here what we 'use', the test should fail always
    - use_rule: bad_use_rule
    """
    with pytest.raises(UseRuleError):
        Configuration(config_yaml, True)


def test_fail_directory_map_missing_trailing_slash():
    """Test missing trailing slash in directory_map entry."""
    config_yaml = r"""
structure_rules:
    license_rule:
        - LICENSE
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
        - LICENSE
directory_map:
  /:
    - use_rule: license_rule
  missing_starting_slash/:
    - use_rule: license_rule
    """
    with pytest.raises(DirectoryStructureError):
        Configuration(config_yaml, True)


def test_fail_old_config_format():
    """Test wrong config format."""
    config_yaml = r"""
structure_rules:
    license_rule:
        files:
            - name: 'LICENSE'
        dirs:
            - name: 'dirname'
directory_map:
  /:
    - use_rule: license_rule
    """
    with pytest.raises(StructureRuleError):
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
