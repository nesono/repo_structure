# pylint: disable=import-error
"""Tests for repo_structure library functions."""
import sys

import pytest
from .repo_structure_config import (
    Configuration,
    UseRuleError,
    ConfigurationParseError,
    DirectoryStructureError,
)


def test_successful_parse():
    """Test successful parsing with many features.

    This is not so much a test than a showroom.
    """
    test_yaml = r"""
structure_rules:
  basic_rule:
    - p: 'README.md'
      required: True
    - p: '[^/]*\.md'
      required: False
    - p: '.github/'
      required: False
      if_exists:
        - p: 'CODEOWNERS'
  recursive_rule:
    - p: '[^/]*\.py'
    - p: 'package/[^/]*'
      use_rule: recursive_rule
templates:
  software_component:
    - p: '{{component_name}}_component.cpp'
    - p: '{{component_name}}_component.h'
    - p: '{{component_name}}_config.h'
      required: False
    - p: '{{component_name}}_factory.cpp'
    - p: '{{component_name}}_factory.h'
    - p: 'BUILD'
    - p: 'README.md'
    - p: 'doc/'
    - p: 'doc/{{component_name}}.swreq.md'
    - p: 'doc/{{component_name}}.techspec.md'
    - p: '[^/]*\_test.cpp'
      required: False
    - p: 'tests/[^/]*_test.cpp'
      required: False
directory_map:
  /:
    - use_rule: basic_rule
    - use_rule: recursive_rule
  /software_components/:
    - use_template: software_component
      parameters:
        component_name: ['lidar', 'camera', 'driver', 'control']
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
    - p: "README.md"

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
    - p: 'README.md'
    # if we use a use_rule, we need to add required/optional, too
    - p: 'docs/'
      required: True
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
    - p: "docs/"
      required: False
      use_rule: documentation
    - p: "docs/[^/]*/"
      required: False
    - p: "docs/[^/]/[^/]*"
      required: False
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
    - p: "README.md"
      bad_key: '.*\.py'
directory_map:
  /:
    - use_rule: bad_key_rule
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_directory_map_key_in_directory_map():
    """Test failing parsing of file mappings using bad key."""
    test_config = """
structure_rules:
    correct_rule:
        - p: 'unused_file'
directory_map:
    /:
        - foo: documentation
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_directory_map_additional_key_in_directory_map():
    """Test failing parsing of file mappings using additional bad key."""
    test_config = """
structure_rules:
    correct_rule:
        - p: 'unused_file'
directory_map:
    /:
        - use_rule: correct_rule
        - foo: documentation
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_use_rule_not_recursive():
    """Test use rule usage not recursive."""
    config_yaml = r"""
structure_rules:
    license_rule:
        - p: 'LICENSE'
    bad_use_rule:
        - p: '.*/'
          required: False
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
        - p: LICENSE
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
        - p: LICENSE
directory_map:
  /:
    - use_rule: license_rule
  missing_starting_slash/:
    - use_rule: license_rule
    """
    with pytest.raises(DirectoryStructureError):
        Configuration(config_yaml, True)


def test_fail_use_template_missing_parameters():
    """Test failing template without parameters."""
    test_config = """
templates:
    some_template:
        - p: '{{parameter_name}}.md'
directory_map:
    /:
        - use_template: some_template
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_use_template_parameters_not_arrays():
    """Test failing template with parameters that are not arrays."""
    test_config = """
templates:
    some_template:
        - p: '{{parameter_name}}.md'
directory_map:
    /:
        - use_template: some_template
          parameters: 'not_an_array'
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_use_template_parameters_with_use_rule():
    """Test failing template with parameters and only have a use_rule."""
    test_config = """
structure_rules:
    correct_rule:
        - p: 'some_file.md'
directory_map:
    /:
        - use_rule: correct_rule
          parameters: ['item1', 'item2']
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


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
    with pytest.raises(ConfigurationParseError):
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
