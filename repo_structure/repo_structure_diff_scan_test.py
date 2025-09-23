# pylint: disable=import-error
# pylint: disable=duplicate-code
"""Tests for diff-scan subcommand."""

from .repo_structure_lib import Flags
from .repo_structure_config import Configuration
from .repo_structure_diff_scan import check_path


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
    assert check_path(config, "README.md") is None
    assert check_path(config, "LICENSE") is None

    issue = check_path(config, "bad_filename.md")
    assert issue is not None
    assert issue.code == "unspecified_entry"

    issue = check_path(config, "CMakeLists.txt")
    assert issue is not None
    assert issue.code == "forbidden_entry"


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
    assert check_path(config, "python/main.py") is None

    issue = check_path(config, "python/bad_filename.py")
    assert issue is not None
    assert issue.code == "unspecified_entry"


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
    assert check_path(config, "main.py") is None
    assert check_path(config, "python/something.py") is None


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
    assert check_path(config, "README.md") is None
    assert check_path(config, "main.py") is None

    issue = check_path(config, "bad_file_name.cpp")
    assert issue is not None
    assert issue.code == "unspecified_entry"


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
    assert check_path(config, "main/main.cpp", flags) is None
    assert check_path(config, "main/main/main.cpp", flags) is None

    issue = check_path(config, "main/main.rs", flags)
    assert issue is not None
    assert issue.code == "unspecified_entry"

    issue = check_path(config, "main/main/main.rs", flags)
    assert issue is not None
    assert issue.code == "unspecified_entry"


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
    assert check_path(config, "app/main.py") is None
    assert check_path(config, "app/lib/lib.py") is None
    assert check_path(config, "app/lib/sub_lib/lib.py") is None
    assert check_path(config, "app/lib/sub_lib/tool/main.py") is None
    assert check_path(config, "app/lib/sub_lib/tool/README.md") is None

    issue = check_path(config, "app/README.md")
    assert issue is not None
    assert issue.code == "unspecified_entry"

    issue = check_path(config, "app/lib/sub_lib/README.md")
    assert issue is not None
    assert issue.code == "unspecified_entry"


def test_skip_file():
    """Test skipping file for diff scan."""
    config_filname = "repo_structure.yaml"
    config = Configuration(config_filname)
    assert check_path(config, "repo_structure.yaml") is None


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
    assert check_path(config, "README.md", flags) is None
    assert check_path(config, "python/main.py", flags) is None
