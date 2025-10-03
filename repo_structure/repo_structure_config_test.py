"""Tests for repo_structure library functions."""

import pytest
from .repo_structure_config import (
    Configuration,
)
from . import ConfigurationParseError
from .repo_structure_lib import StructureRuleError, TemplateError


def test_successful_parse():
    """Test successful parsing with many features.

    This is not so much a test than a showroom.
    """
    test_yaml = r"""
structure_rules:
  basic_rule:
    - description: 'Basic rules for common project files'
    - require: 'README\.md'
    - allow: '.*\.md'
    - forbid: 'CMakeLists\.txt'
    - allow: '.github/'
      if_exists:
        - require: 'CODEOWNERS'
  recursive_rule:
    - description: 'Recursive Python package structure'
    - require: '.*\.py'
    - require: 'package/'
      if_exists:
      - require: '.*/'
        use_rule: recursive_rule
templates:
  software_component:
    - description: 'Template for software component structure'
    - require: '{{component_name}}_component.cpp'
    - require: '{{component_name}}_component.h'
    - allow: '{{component_name}}_config.h'
    - require: '{{component_name}}_factory.cpp'
    - require: '{{component_name}}_factory.h'
    - require: 'BUILD'
    - require: 'README.md'
    - require: 'doc/'
      if_exists:
      - require: '{{component_name}}.swreq.md'
      - require: '{{component_name}}.techspec.md'
    - allow: '.*\_test.cpp'
    - allow: 'tests/.*_test.cpp'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule
    - use_rule: recursive_rule
  /software_components/:
    - description: 'Software components directory'
    - use_template: software_component
      parameters:
        component_name: ['lidar', 'camera', 'driver', 'control']
  /repo_struct/:
    - description: 'Repository structure directory'
    - use_rule: ignore
    """
    # parsing should not throw using the above yaml
    config = Configuration(test_yaml, True)

    # assert on basics
    assert config is not None
    assert config.directory_map is not None
    assert config.structure_rules is not None


def test_success_minimal_parse_with_config_file():
    """Test successful parsing with minimal configuration file."""
    config = Configuration("repo_structure/test_config_allow_all.yaml")
    assert config is not None


def test_fail_parse_bad_pattern():
    """Test failing parsing due to a bad schema string."""
    test_yaml = r"""
structure_rules:
  bad_pattern_rule:
    - description: 'Bad pattern rule'
    - require: "[^]*.md"

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: bad_pattern_rule
    """

    with pytest.raises(StructureRuleError):
        Configuration(test_yaml, True)


def test_fail_parse_bad_schema():
    """Test failing parsing due to a bad schema string."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure'
    - require: "README.md"

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """

    bad_schema = {
        "type": "object",
        "properties": {"countryName": {"type": "stri"}},
        "required": ["locality"],
    }
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True, bad_schema)


def test_fail_parse_empty_structure_rule():
    """Test failing parsing when structure rules is empty."""
    test_yaml = r"""
structure_rules:
  base_structure:

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_missing_description_in_structure_rule():
    """Test failing parsing when structure rule is missing description."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - require: "README.md"

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_missing_description_in_directory_map():
    """Test failing parsing when directory map is missing description."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure'
    - require: "README.md"

directory_map:
  /:
    - use_rule: base_structure
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_missing_description_in_template():
    """Test failing parsing when template is missing description."""
    test_yaml = r"""
templates:
  some_template:
    - require: '{{param}}.md'

directory_map:
  /:
    - description: 'Root directory'
    - use_template: some_template
      parameters:
        param: ['test']
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_double_description_in_structure_rule():
    """Test failing parsing when structure rule has two description entries."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - description: 'First description'
    - description: 'Second description'
    - require: "README.md"

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_double_description_in_directory_map():
    """Test failing parsing when directory map has two description entries."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure'
    - require: "README.md"

directory_map:
  /:
    - description: 'First description'
    - description: 'Second description'
    - use_rule: base_structure
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_description_not_first_in_structure_rule():
    """Test failing parsing when description is not the first entry in structure rule."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - require: "README.md"
    - description: 'Base structure'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_description_not_first_in_directory_map():
    """Test failing parsing when description is not the first entry in directory map."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure'
    - require: "README.md"

directory_map:
  /:
    - use_rule: base_structure
    - description: 'Root directory'
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_dangling_use_rule_in_directory_map():
    """Test failing parsing of the structure rules with dangling use_rule."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure'
    - require: "README.md"

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    - use_rule: python_package
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_parse_dangling_use_rule_in_structure_rule():
    """Test failing parsing of the structure rules with dangling use_rule."""
    test_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure'
    - require: 'README.md'
    - allow: 'docs/'
      use_rule: python_package

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_yaml, True)


def test_fail_directory_structure_mixing_use_rule_and_files():
    """Test failing parsing of directory when use_rule and files are mixed."""
    test_config = r"""
structure_rules:
  package:
    - description: 'Package structure'
    - allow: "docs/"
      use_rule: documentation
      if_exists:
      - allow: ".*/"
        if_exists:
        - allow: ".*"
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: package
"""
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_parse_bad_key_in_structure_rule():
    """Test failing parsing of file dependencies using bad key."""
    test_config = r"""
structure_rules:
  bad_key_rule:
    - description: 'Bad key rule'
    - require: "README.md"
      bad_key: '.*\.py'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: bad_key_rule
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_directory_map_key_in_directory_map():
    """Test failing parsing of file mappings using bad key."""
    test_config = """
structure_rules:
    correct_rule:
        - description: 'Correct rule'
        - require: 'unused_file'
directory_map:
    /:
        - description: 'Root directory'
        - foo: documentation
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_directory_map_additional_key_in_directory_map():
    """Test failing parsing of file mappings using additional bad key."""
    test_config = """
structure_rules:
    correct_rule:
        - description: 'Correct rule'
        - require: 'unused_file'
directory_map:
    /:
        - description: 'Root directory'
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
        - description: 'License rule'
        - require: 'LICENSE'
    bad_use_rule:
        - description: 'Bad use rule'
        - allow: '.*/'
          use_rule: license_rule
directory_map:
  /:
    # it doesn't matter here what we 'use', the test should fail always
    - description: 'Root directory'
    - use_rule: bad_use_rule
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(config_yaml, True)


def test_fail_directory_map_missing_trailing_slash():
    """Test missing trailing slash in directory_map entry."""
    config_yaml = r"""
structure_rules:
    license_rule:
        - description: 'License rule'
        - require: LICENSE
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: license_rule
  /missing_trailing_slash:
    - description: 'Missing trailing slash'
    - use_rule: license_rule
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(config_yaml, True)


def test_fail_directory_map_missing_starting_slash():
    """Test missing starting slash in directory_map entry."""
    config_yaml = r"""
structure_rules:
    license_rule:
        - description: 'License rule'
        - require: LICENSE
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: license_rule
  missing_starting_slash/:
    - description: 'Missing starting slash'
    - use_rule: license_rule
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(config_yaml, True)


def test_fail_use_template_missing_parameters():
    """Test failing template without parameters."""
    test_config = """
templates:
    some_template:
        - description: 'Some template'
        - require: '{{parameter_name}}.md'
directory_map:
    /:
        - description: 'Root directory'
        - use_template: some_template
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_use_template_parameters_not_arrays():
    """Test failing template with parameters that are not arrays."""
    test_config = """
templates:
    some_template:
        - description: 'Some template'
        - require: '{{parameter_name}}.md'
directory_map:
    /:
        - description: 'Root directory'
        - use_template: some_template
          parameters:
            param_1: 'not_an_array'
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_use_template_bad_template_reference():
    """Test failing template with bad template reference."""
    test_config = """
templates:
    some_template:
        - description: 'Template description'
        - require: '{{parameter_name}}.md'
directory_map:
    /:
        - description: 'Root directory'
        - use_template: bad_reference
          parameters:
            param_1: ['some_param']
    """
    with pytest.raises(TemplateError):
        Configuration(test_config, True)


def test_fail_use_template_parameters_with_use_rule():
    """Test failing template with parameters and only have a use_rule."""
    test_config = """
structure_rules:
    correct_rule:
        - description: 'Correct rule'
        - require: 'some_file.md'
directory_map:
    /:
        - description: 'Root directory'
        - use_rule: correct_rule
          parameters:
            param_1: ['item1', 'item2']
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_double_underscore_prefix_structure_rule():
    """Test failing template with parameters and only have a use_rule."""
    test_config = """
structure_rules:
    __incorrect_rule:
        - description: 'Incorrect rule'
        - require: 'some_file.md'
directory_map:
    /:
        - description: 'Root directory'
        - use_rule: __incorrect_rule
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_double_underscore_prefix_template():
    """Test failing template with parameters and only have a use_rule."""
    test_config = """
templates:
    __incorrect_template:
        - description: 'Incorrect template'
        - require: '{{parameter}}_some_file.md'
directory_map:
    /:
        - description: 'Root directory'
        - use_rule: __incorrect_template
          parameters:
            parameter: ['item1']
    """
    with pytest.raises(ConfigurationParseError):
        Configuration(test_config, True)


def test_fail_old_config_format():
    """Test wrong config format."""
    config_yaml = r"""
structure_rules:
    license_rule:
        - description: 'License rule'
        - files:
            - name: 'LICENSE'
        - dirs:
            - name: 'dirname'
directory_map:
  /:
    - description: 'Root directory'
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


def test_requires_companion_parsing():
    """Test that requires_companion is properly parsed in the schema and config."""
    test_yaml = r"""
structure_rules:
  cpp_with_headers:
    - description: 'C++ files with required headers'
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: '{{base}}.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_headers
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)

    # Verify the rule was parsed
    assert "cpp_with_headers" in config.structure_rules
    rules = config.structure_rules["cpp_with_headers"]

    # Find the .cpp pattern
    cpp_rule = next((r for r in rules if r.path.pattern.endswith(r"\.cpp")), None)
    assert cpp_rule is not None
    assert len(cpp_rule.requires_companion) == 1

    # Check the companion requirement
    companion = cpp_rule.requires_companion[0]
    assert companion.path.pattern == "{{base}}.h"
    assert companion.is_required
