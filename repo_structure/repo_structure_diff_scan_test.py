# pylint: disable=import-error
# pylint: disable=duplicate-code
"""Tests for diff-scan subcommand."""

import pytest


from .repo_structure_lib import UnspecifiedEntryError, Flags
from .repo_structure_config import Configuration
from .repo_structure_diff_scan import assert_path


def test_matching_regex():
    """Test with required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    assert_path(config, "README.md")
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "bad_filename.md")


def test_matching_regex_dir():
    """Test with required file."""
    config_yaml = r"""
structure_rules:
  recursive_rule:
    - require: 'main\.py'
    - require: 'python/'
      use_rule: recursive_rule
directory_map:
  /:
    - use_rule: recursive_rule
    """
    config = Configuration(config_yaml, True)
    assert_path(config, "python/main.py")
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "python/bad_filename.py")


def test_multi_use_rule():
    """Test multiple use rules."""
    config_yaml = r"""
structure_rules:
  base_structure:
      - p: 'README\.md'
  python_package:
      - p: '[^/]*?\.py'
directory_map:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    assert_path(config, "README.md")
    assert_path(config, "main.py")


def test_multi_use_rule_fail():
    """Test multi use rule diff scan fail."""
    config_yaml = r"""
structure_rules:
  base_structure:
      - p: 'README\.md'
  python_package:
      - p: '[^/]*?\.py'
directory_map:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    assert_path(config, "README.md")
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "main.cpp")  # bad file name


def test_use_rule_recursive():
    """Test self-recursion from a use rule."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - p: 'README\.md'
  cpp_source:
    - p: '[^/]*?\.cpp'
    - p: '[^/]*?/'
      required: False
      use_rule: cpp_source
directory_map:
  /:
    - use_rule: base_structure
    - use_rule: cpp_source
    """
    flags = Flags()
    flags.verbose = True
    config = Configuration(config_yaml, True)
    assert_path(config, "main/main.cpp", flags)
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "main/main.rs", flags)


def test_succeed_elaborate_use_rule_recursive():
    """Test deeper nested use rule setup with existing entries."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - p: 'README\.md'
  python_package:
    - p: '[^/]*?\.py'
    - p: '[^/]*?/'
      required: False
      use_rule: python_package
directory_map:
  /:
    - use_rule: base_structure
  /app/:
    - use_rule: python_package
  /app/lib/sub_lib/tool/:
    - use_rule: python_package
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    assert_path(config, "app/main.py")
    assert_path(config, "app/lib/lib.py")
    assert_path(config, "app/lib/sub_lib/lib.py")
    assert_path(config, "app/lib/sub_lib/tool/main.py")
    assert_path(config, "app/lib/sub_lib/tool/README.md")
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "app/README.md")
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "app/lib/sub_lib/README.md")
