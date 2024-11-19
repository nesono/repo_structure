# pylint: disable=import-error
# pylint: disable=duplicate-code
"""Tests for diff-scan subcommand."""

import pytest


from .repo_structure_lib import UnspecifiedEntryError, Flags, ForbiddenEntryError
from .repo_structure_config import Configuration
from .repo_structure_diff_scan import assert_path


def test_matching_regex():
    """Test with required, forbidden, and allowed file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - require: 'README\.md'
    - forbid: 'CMakeLists\.txt'
    - allow: 'LICENSE'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    assert_path(config, "README.md")
    assert_path(config, "LICENSE")
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "bad_filename.md")
    with pytest.raises(ForbiddenEntryError):
        assert_path(config, "CMakeLists.txt")


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


def test_matching_regex_dir_if_exists():
    """Test with required file."""
    config_yaml = r"""
structure_rules:
  recursive_rule:
    - require: 'main\.py'
    - require: 'python/'
      if_exists:
        - require: '.*'
directory_map:
  /:
    - use_rule: recursive_rule
    """
    config = Configuration(config_yaml, True)
    assert_path(config, "main.py")
    assert_path(config, "python/something.py")


def test_multi_use_rule():
    """Test multiple use rules."""
    config_yaml = r"""
structure_rules:
  base_structure:
      - require: 'README\.md'
  python_package:
      - require: '.*\.py'
directory_map:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    assert_path(config, "README.md")
    assert_path(config, "main.py")
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "bad_file_name.cpp")


def test_use_rule_recursive():
    """Test self-recursion from a use rule."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - require: 'README\.md'
  cpp_source:
    - require: '.*\.cpp'
    - allow: '.*/'
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
    assert_path(config, "main/main/main.cpp", flags)
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "main/main.rs", flags)
    with pytest.raises(UnspecifiedEntryError):
        assert_path(config, "main/main/main.rs", flags)


def test_succeed_elaborate_use_rule_recursive():
    """Test deeper nested use rule setup with existing entries."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - require: 'README\.md'
  python_package:
    - require: '.*\.py'
    - allow: '.*/'
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


def test_skip_file():
    """Test skipping file for diff scan."""
    config_filname = "repo_structure.yaml"
    config = Configuration(config_filname)
    assert_path(config, "repo_structure.yaml")


def test_ignore_rule():
    """Test with ignored directory."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
  /python/:
    - use_rule: ignore
        """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.verbose = True
    assert_path(config, "README.md", flags)
    assert_path(config, "python/main.py", flags)
