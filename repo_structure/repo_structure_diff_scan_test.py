# pylint: disable=duplicate-code
"""Tests for diff-scan subcommand."""

from .repo_structure_lib import Flags
from .repo_structure_config import Configuration
from .repo_structure_diff_scan import DiffScanProcessor


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
    processor = DiffScanProcessor(config)
    assert processor.check_path("README.md") is None
    assert processor.check_path("LICENSE") is None

    issue = processor.check_path("bad_filename.md")
    assert issue is not None
    assert issue.code == "unspecified_entry"

    issue = processor.check_path("CMakeLists.txt")
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
    processor = DiffScanProcessor(config)
    assert processor.check_path("python/main.py") is None

    issue = processor.check_path("python/bad_filename.py")
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
    processor = DiffScanProcessor(config)
    assert processor.check_path("main.py") is None
    assert processor.check_path("python/something.py") is None


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
    processor = DiffScanProcessor(config)
    assert processor.check_path("README.md") is None
    assert processor.check_path("main.py") is None

    issue = processor.check_path("bad_file_name.cpp")
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
    processor = DiffScanProcessor(config, flags)
    assert processor.check_path("main/main.cpp") is None
    assert processor.check_path("main/main/main.cpp") is None

    issue = processor.check_path("main/main.rs")
    assert issue is not None
    assert issue.code == "unspecified_entry"

    issue = processor.check_path("main/main/main.rs")
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
    processor = DiffScanProcessor(config)
    assert processor.check_path("app/main.py") is None
    assert processor.check_path("app/lib/lib.py") is None
    assert processor.check_path("app/lib/sub_lib/lib.py") is None
    assert processor.check_path("app/lib/sub_lib/tool/main.py") is None
    assert processor.check_path("app/lib/sub_lib/tool/README.md") is None

    issue = processor.check_path("app/README.md")
    assert issue is not None
    assert issue.code == "unspecified_entry"

    issue = processor.check_path("app/lib/sub_lib/README.md")
    assert issue is not None
    assert issue.code == "unspecified_entry"


def test_skip_file():
    """Test skipping file for diff scan."""
    config_filname = "repo_structure.yaml"
    config = Configuration(config_filname)
    processor = DiffScanProcessor(config)
    assert processor.check_path("repo_structure.yaml") is None


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
    processor = DiffScanProcessor(config, flags)
    assert processor.check_path("README.md") is None
    assert processor.check_path("python/main.py") is None


def test_check_paths_batch():
    """Test the check_paths method for batch processing."""
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
    processor = DiffScanProcessor(config)

    # Test with all valid paths
    valid_paths = ["README.md", "LICENSE"]
    issues = processor.check_paths(valid_paths)
    assert len(issues) == 0

    # Test with mixed valid and invalid paths
    mixed_paths = [
        "README.md",
        "invalid.py",
        "LICENSE",
        "CMakeLists.txt",
        "another_invalid.txt",
    ]
    issues = processor.check_paths(mixed_paths)
    assert len(issues) == 3

    # Check specific issues
    issue_codes = {issue.code for issue in issues}
    assert "unspecified_entry" in issue_codes
    assert "forbidden_entry" in issue_codes

    # Check specific paths
    issue_paths = {issue.path for issue in issues}
    assert "invalid.py" in issue_paths
    assert "CMakeLists.txt" in issue_paths
    assert "another_invalid.txt" in issue_paths
