# pylint: disable=duplicate-code
"""Tests for diff-scan subcommand."""

from .repo_structure_lib import Flags
from .repo_structure_config import Configuration
from .repo_structure_diff_scan import DiffScanProcessor
from .repo_structure_test_lib import with_repo_structure_in_tmpdir


def test_matching_regex():
    """Test with required, forbidden, and allowed file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with various file rules'
    - require: 'README\.md'
    - forbid: 'CMakeLists\.txt'
    - allow: 'LICENSE'
directory_map:
  /:
    - description: 'Root directory'
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
    - description: 'Recursive Python rule'
    - require: 'main\.py'
    - require: 'python/'
      use_rule: recursive_rule
directory_map:
  /:
    - description: 'Root directory'
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
    - description: 'Recursive rule with if_exists'
    - require: 'main\.py'
    - require: 'python/'
      if_exists:
        - require: '.*'
directory_map:
  /:
    - description: 'Root directory'
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
      - description: 'Base structure with README'
      - require: 'README\.md'
  python_package:
      - description: 'Python package structure'
      - require: '.*\.py'
directory_map:
  /:
    - description: 'Root directory'
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
    - description: 'Base structure with README'
    - require: 'README\.md'
  cpp_source:
    - description: 'C++ source files'
    - require: '.*\.cpp'
    - allow: '.*/'
      use_rule: cpp_source
directory_map:
  /:
    - description: 'Root directory'
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
    - description: 'Base structure with README'
    - require: 'README\.md'
  python_package:
    - description: 'Python package structure'
    - require: '.*\.py'
    - allow: '.*/'
      use_rule: python_package
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
  /app/:
    - description: 'Application directory'
    - use_rule: python_package
  /app/lib/sub_lib/tool/:
    - description: 'Tool directory'
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
    config_yaml = r"""
structure_rules:
    base_structure:
    - description: 'Base structure with README'
    - require: 'README\.md'
directory_map:
    /:
    - description: 'Root directory'
    - use_rule: base_structure
"""
    config = Configuration(config_yaml, param1_is_yaml_string=True)
    processor = DiffScanProcessor(config)
    assert processor.check_path(".gitignore") is None


def test_ignore_rule():
    """Test with ignored directory."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with README'
    - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
  /python/:
    - description: 'Python directory'
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
    - description: 'Base structure with various file rules'
    - require: 'README\.md'
    - forbid: 'CMakeLists\.txt'
    - allow: 'LICENSE'
directory_map:
  /:
    - description: 'Root directory'
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


@with_repo_structure_in_tmpdir(
    """
widget.cpp
widget.h
engine.cpp
"""
)
def test_requires_companion_check():
    """Test that requires_companion validates companion files exist."""
    test_yaml = r"""
structure_rules:
  cpp_with_headers:
    - description: 'C++ files with required headers'
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: '{{base}}.h'
    - allow: '.*\.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_headers
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    scanner = DiffScanProcessor(config)

    # widget.cpp should pass (has widget.h)
    issue = scanner.check_path("widget.cpp")
    assert issue is None

    # engine.cpp should fail (missing engine.h)
    issue = scanner.check_path("engine.cpp")
    assert issue is not None
    assert "engine.h" in issue.message
    assert "Missing required companion" in issue.message


@with_repo_structure_in_tmpdir(
    """
lib.cpp
lib.h
lib_test.cpp
util.cpp
util.h
"""
)
def test_requires_companion_multiple():
    """Test multiple companion requirements."""
    test_yaml = r"""
structure_rules:
  cpp_with_test:
    - description: 'C++ with header and test'
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: '{{base}}.h'
        - require: '{{base}}_test.cpp'
    - allow: '.*\.h'
    - allow: '.*_test\.cpp'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_test
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    scanner = DiffScanProcessor(config)

    # lib.cpp should pass (has both companions)
    issue = scanner.check_path("lib.cpp")
    assert issue is None

    # util.cpp should fail (missing util_test.cpp)
    issue = scanner.check_path("util.cpp")
    assert issue is not None
    assert "util_test.cpp" in issue.message


@with_repo_structure_in_tmpdir(
    """
widget.cpp
include/
include/widget.h
engine.cpp
"""
)
def test_requires_companion_subdirectory():
    """Test that companions can be in subdirectories."""
    test_yaml = r"""
structure_rules:
  cpp_with_header_in_include:
    - description: 'C++ with header in include subdir'
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: 'include/{{base}}.h'
    - allow: '.*\.cpp'
    - allow: 'include/'
      if_exists:
        - allow: '.*\.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_header_in_include
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    scanner = DiffScanProcessor(config)

    # widget.cpp should pass (has include/widget.h)
    issue = scanner.check_path("widget.cpp")
    assert issue is None

    # engine.cpp should fail (missing include/engine.h)
    issue = scanner.check_path("engine.cpp")
    assert issue is not None
    assert "include/engine.h" in issue.message
