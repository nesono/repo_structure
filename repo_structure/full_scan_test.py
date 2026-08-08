# pylint: disable=duplicate-code
# pylint: disable=too-many-lines
"""Tests for repo_structure library functions."""

import pytest

from .config import Configuration
from .full_scan import (
    FullScanProcessor,
    ScanIssue,
)
from .errors import ConfigurationParseError
from .models import Flags

from .test_lib import create_repo_structure


def _check_repo_directory_structure(
    repo_root: str,
    config: Configuration,
    flags: Flags = Flags(),
) -> tuple[list[ScanIssue], list[ScanIssue]]:
    """Check repository structure and return errors and warnings instead of asserting."""
    processor = FullScanProcessor(repo_root, config, flags)
    result = processor.scan()
    return result.errors, result.warnings


def test_all_empty():
    """Test empty spec."""
    config_yaml = r"""
"""
    with pytest.raises(ConfigurationParseError):
        Configuration.from_yaml_string(config_yaml)


def test_matching_regex(tmp_path):
    """Test with required file."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with markdown files'
    - require: '.*\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_required_dir(tmp_path):
    """Test with required directory."""
    repo = create_repo_structure(
        tmp_path,
        """
python/
python/main.py
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with Python directory'
    - require: 'python/'
      if_exists:
      - allow: '.*\.py'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
        """
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_unspecified_dir(tmp_path):
    """Test with unspecified directory in directory, where only files are allowed."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
python/
python/main.py
unspecified/
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with required files'
    - require: "README.md"
    - require: "python/"
      if_exists:
      - require: '.*'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
        """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "unspecified_entry"
    assert "unspecified" in errors[0].path


def test_missing_root_mapping(tmp_path):
    """Test missing root mapping."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
      - description: 'Base structure rule'
      - require: "irrelevant"
directory_map:
  /some_dir/:
    - description: 'Some directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_root_mapping"


def test_missing_required_file(tmp_path):
    """Test missing required file."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with required files'
    - require: "LICENSE"
    - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


def test_missing_required_dir(tmp_path):
    """Test missing required directory."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with Python directory'
    - require: 'README\.md'
    - require: 'python/'
      if_exists:
      - require: '.*'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
        """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


def test_fail_rule_precedence(tmp_path):
    """Test rule precedence. This needs to fail because the wildcard consumes all matches.

    The first match wins and thus the README.md will never be reached."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with wildcard'
    - require: '.*'
    - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


def test_multi_use_rule(tmp_path):
    """Test using multiple rules."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
main.py
""",
    )
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
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_multi_use_rule_missing_py_file(tmp_path):
    """Test missing required pattern file while using multi rules."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )
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
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


def test_conflicting_file_and_dir_names(tmp_path):
    """Test two required entries, one file, one dir. Need to pass ensuring distinct detection."""
    repo = create_repo_structure(
        tmp_path,
        """
filename.txt
dirname/
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
      - description: 'Base structure with name patterns'
      - require: '.*name.*'
      - require: '.*name.*/'
        if_exists:
        - allow: '.*'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_conflicting_dir_name(tmp_path):
    """Ensure that a matching directory does not suffice a required file."""
    repo = create_repo_structure(
        tmp_path,
        """
dirname/
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with name pattern'
    - require: '.*name.*'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 2
    assert errors[0].code == "missing_required_entries"
    assert errors[1].code == "unspecified_entry"


def test_conflicting_file_name(tmp_path):
    """Ensure that a matching file does not suffice a required directory."""
    repo = create_repo_structure(
        tmp_path,
        """
filename.txt
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with directory pattern'
    - require: '.*name.*/'
      if_exists:
      - allow: '.*'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 2
    assert errors[0].code == "missing_required_entries"
    assert errors[1].code == "unspecified_entry"


def test_filename_with_bad_substring_match(tmp_path):
    """Ensure substring match is not enough to match."""
    repo = create_repo_structure(
        tmp_path,
        """
filename.txt
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with name pattern'
    - require: '.*name'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 2
    assert errors[0].code == "missing_required_entries"
    assert errors[1].code == "unspecified_entry"


def test_required_file_in_optional_directory_no_entry(tmp_path):
    """Test required file under optional directory - no entry."""
    repo = create_repo_structure(
        tmp_path,
        """
LICENSE
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with optional doc directory'
    - require: 'LICENSE'
    - allow: 'doc/'
      if_exists:
        - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_required_file_in_optional_directory_with_entry(tmp_path):
    """Test required file under optional directory - with directory entry."""
    repo = create_repo_structure(
        tmp_path,
        """
LICENSE
doc/
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with optional doc directory'
    - require: 'LICENSE'
    - allow: 'doc/'
      if_exists:
        - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


def test_required_file_in_optional_directory_with_entry_and_exists(tmp_path):
    """Test required file under optional directory - with directory entry and file."""
    repo = create_repo_structure(
        tmp_path,
        """
LICENSE
doc/
doc/README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with optional doc directory'
    - require: 'LICENSE'
    - allow: 'doc/'
      if_exists:
        - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_use_rule_recursive(tmp_path):
    """Test self-recursion from a use rule."""
    repo = create_repo_structure(
        tmp_path,
        """
main.cpp
README.md
lib/
lib/lib.cpp
""",
    )
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
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_fail_use_rule_recursive(tmp_path):
    """Ensure use_rules are not mixed up in recursion."""
    repo = create_repo_structure(
        tmp_path,
        """
main.py
README.md
lib/
lib/README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with README'
    - require: 'README\.md'
  python_package:
    - description: 'Python package structure'
    - require: '.*\.py'
    - require: '.*/'
      use_rule: python_package
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 2
    assert errors[0].code == "missing_required_entries"
    assert errors[0].path == "lib"
    assert errors[1].code == "unspecified_entry"
    assert errors[1].path == "lib/README.md"


def test_fail_directory_mapping_precedence(tmp_path):
    """Test that directories from directory_mapping take precedence."""
    repo = create_repo_structure(
        tmp_path,
        """
main.py
README.md
lib/
lib/README.md
""",
    )
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
    - use_rule: python_package
  /lib/:
    - description: 'Library directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_succeed_elaborate_use_rule_recursive(tmp_path):
    """Test deeper nested use rule setup with existing entries."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
app/
app/main.py
app/lib/
app/lib/lib.py
app/lib/sub_lib/
app/lib/sub_lib/lib.py
app/lib/sub_lib/tool/
app/lib/sub_lib/tool/README.md
app/lib/sub_lib/tool/main.py
""",
    )
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
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_succeed_ignored_hidden_file(tmp_path):
    """Test existing ignored hidden file - hidden files not tracked."""
    repo = create_repo_structure(
        tmp_path,
        """
.hidden.md
README.md
""",
    )
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
    config = Configuration.from_yaml_string(config_yaml)
    flags = Flags()
    flags.include_hidden = False
    errors, warnings = _check_repo_directory_structure(repo, config, flags)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_fail_hidden_file_required_despite_hidden_disabled(tmp_path):
    """Test with a missing, required, hidden file - hidden files not tracked."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
     - description: 'Base structure with hidden files'
     - require: '\.hidden\.md'
     - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    flags = Flags()
    flags.include_hidden = True
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


def test_fail_unspecified_hidden_files_when_hidden_enabled(tmp_path):
    """Test for unspecified hidden file - hidden files tracked."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
.hidden.md
.unspecified.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with hidden files'
    - require: '\.hidden.md'
    - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    flags = Flags()
    flags.include_hidden = True
    errors, _ = _check_repo_directory_structure(repo, config, flags)
    assert len(errors) == 1
    assert errors[0].code == "unspecified_entry"


def test_succeed_gitignored_file(tmp_path):
    """Test for ignored file from gitignore."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
ignored.md
.gitignore:ignored.md
""",
    )
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
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_succeed_gitignored_file_in_subdirectory(tmp_path):
    """Test that gitignore patterns are matched against the full relative path."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
python/
python/main.py
python/ignored.md
.gitignore:python/ignored.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with README'
    - require: 'README\.md'
    - require: 'python/'
      if_exists:
      - require: 'main\.py'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_fail_unspecified_link(tmp_path):
    """Test for unspecified symlink."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
link -> README.md
""",
    )
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
    config = Configuration.from_yaml_string(config_yaml)
    flags = Flags()
    flags.follow_symlinks = True
    errors, warnings = _check_repo_directory_structure(repo, config, flags)
    assert len(errors) == 1
    assert errors[0].code == "unspecified_entry"
    assert len(warnings) == 0


def test_succeed_specified_link(tmp_path):
    """Test for specified symlink."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
link -> README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with symlink'
    - require: 'README\.md'
    - require: 'link'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    flags = Flags()
    flags.follow_symlinks = True
    errors, warnings = _check_repo_directory_structure(repo, config, flags)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_succeed_template_rule(tmp_path):
    """Test template with single parameter."""
    repo = create_repo_structure(
        tmp_path,
        """
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/doc/
driver/doc/driver.techspec.md
""",
    )
    config_yaml = r"""
templates:
  component:
    - description: 'Component template'
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_fail_template_rule_missing_file(tmp_path):
    """Test template with single parameter missing file."""
    repo = create_repo_structure(
        tmp_path,
        """
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/doc/
""",
    )
    config_yaml = r"""
templates:
  component:
    - description: 'Component template'
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


def test_succeed_template_rule_if_exists(tmp_path):
    """Test template with if_exists clause and optional dir missing."""
    repo = create_repo_structure(
        tmp_path,
        """
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/
""",
    )
    config_yaml = r"""
templates:
  component:
    - description: 'Component template'
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - allow: 'doc/'
        if_exists:
          - require: '{{component}}.techspec.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_succeed_template_rule_subdirectory_map(tmp_path):
    """Test template with single parameter and subdirectory map."""
    repo = create_repo_structure(
        tmp_path,
        """
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/doc/
driver/doc/driver.techspec.md
subdir/control/
subdir/control/control_component.py
subdir/control/doc/
subdir/control/doc/control.techspec.md
subdir/camera/
subdir/camera/camera_component.py
subdir/camera/doc/
subdir/camera/doc/camera.techspec.md
""",
    )
    config_yaml = r"""
templates:
  component:
    - description: 'Component template'
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
  /subdir/:
    - description: 'Subdirectory'
    - use_template: component
      parameters:
        component: ['control', 'camera']
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_fail_template_rule_subdirectory_map_missing_file(tmp_path):
    """Test template with single parameter and subdirectory map missing file."""
    repo = create_repo_structure(
        tmp_path,
        """
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/doc/
driver/doc/driver.techspec.md
subdir/control/
subdir/control/control_component.py
subdir/control/doc/
subdir/camera/
subdir/camera/camera_component.py
subdir/camera/doc/
subdir/camera/doc/camera.techspec.md
""",
    )
    config_yaml = r"""
templates:
  component:
    - description: 'Component template'
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
  /subdir/:
    - description: 'Subdirectory'
    - use_template: component
      parameters:
        component: ['control', 'camera']
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


def test_succeed_template_rule_multiple_expansions(tmp_path):
    """Test template with single parameter and subdirectory map."""
    repo = create_repo_structure(
        tmp_path,
        """
lidar/
lidar/lidar_component.rs
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.rs
driver/doc/
driver/doc/driver.techspec.md
subdir/control/
subdir/control/control_component.py
subdir/control/doc/
subdir/control/doc/control.techspec.md
subdir/camera/
subdir/camera/camera_component.py
subdir/camera/doc/
subdir/camera/doc/camera.techspec.md
""",
    )
    config_yaml = r"""
templates:
  example_template:
    - description: 'Example template with multiple expansions'
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.{{extension}}'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_template: example_template
      parameters:
        component: ['lidar', 'driver']
        extension: ['rs']
  /subdir/:
    - description: 'Subdirectory'
    - use_template: example_template
      parameters:
        component: ['control', 'camera']
        extension: ['py']
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_succeed_with_verbose(tmp_path):
    """Test enforcement with verbose flag enabled."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
link_to_skip -> README.md
doc/
doc/README.md
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with README'
    - require: 'README\.md'
    - allow: 'doc/'
      use_rule: base_structure
templates:
  component:
    - description: 'Component template'
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - allow: 'doc/'
        if_exists:
          - require: '{{component}}.techspec.md'
          - forbid: 'CMakeLists\.txt'
directory_map:
  /:
    - description: 'Root directory'
    - use_template: component
      parameters:
        component: ['lidar']
    - use_rule: base_structure
"""
    flags = Flags()
    flags.verbose = True
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config, flags)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_forbid_file(tmp_path):
    """Test with required directory."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
CMakeLists.txt
python/
python/main.py
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with forbidden file'
    - require: 'README\.md'
    - forbid: 'CMakeLists\.txt'
    - require: 'python/'
      if_exists:
      - require: '.*\.py'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
        """
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)
    assert len(errors) == 1
    assert errors[0].code == "forbidden_entry"


def test_ignore_rule(tmp_path):
    """Test with ignored directory."""
    repo = create_repo_structure(
        tmp_path,
        """
README.md
python/
python/whatever.py
python/this_is_ignored.py
""",
    )
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
    flags = Flags()
    flags.verbose = True
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config, flags)
    assert len(errors) == 0
    assert len(warnings) == 0


def test_warn_on_unused_structure_rule(
    tmp_path,
):  # pylint: disable=import-outside-toplevel
    """Warn if a structure rule exists in the configuration but is never used in the scan.

    Using the non-throwing API, warnings are returned as ScanIssue entries.
    """
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure with README'
    - require: 'README\\.md'
  unused_rule:
    - description: 'Unused rule'
    - allow: 'NEVER_MATCHES\\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
    """
    config = Configuration.from_yaml_string(config_yaml)
    processor = FullScanProcessor(repo, config, Flags())
    warnings = processor.scan().warnings
    assert any(
        "unused_rule" in i.message for i in warnings
    ), f"Expected unused rule warning, got: {warnings}"


def test_companion_full_scan(tmp_path):
    """Test that full scan detects missing companion files."""
    repo = create_repo_structure(
        tmp_path,
        """
widget.cpp
widget.h
engine.cpp
""",
    )
    config_yaml = r"""
structure_rules:
  cpp_with_headers:
    - description: 'C++ files with required headers'
    - allow: '(?P<base>.*)\.cpp'
      companion:
        - require: '{{base}}.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_headers
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)

    # Should have error for engine.cpp missing engine.h
    # Note: We get 2 errors - one from companion check, one from missing required pattern
    # This is expected since companions are added to backlog as required
    companion_errors = [e for e in errors if e.code == "missing_companion"]
    assert len(companion_errors) == 1
    assert companion_errors[0].path == "engine.cpp"
    assert "engine.h" in companion_errors[0].message


def test_companion_subdirectory_full_scan(tmp_path):
    """Test that full scan detects missing companions in subdirectories."""
    repo = create_repo_structure(
        tmp_path,
        """
widget.cpp
widget.h
include/
include/engine.h
engine.cpp
""",
    )
    config_yaml = r"""
structure_rules:
  cpp_with_header_in_include:
    - description: 'C++ with header in include subdir'
    - allow: '(?P<base>.*)\.cpp'
      companion:
        - require: 'include/{{base}}.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_header_in_include
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)

    # Should have errors:
    # 1. widget.cpp missing include/widget.h companion
    # 2. widget.h is unspecified (doesn't match any pattern)
    # 3. Companions are added as required, so missing ones show up
    companion_errors = [e for e in errors if e.code == "missing_companion"]
    assert len(companion_errors) == 1
    assert companion_errors[0].path == "widget.cpp"
    assert "include/widget.h" in companion_errors[0].message


def test_companion_no_expansion(tmp_path):
    """Test that companion works without named groups."""
    repo = create_repo_structure(
        tmp_path,
        """
widget.cpp
include/
include/gadget.h
""",
    )
    config_yaml = r"""
structure_rules:
    cpp_with_header_in_include:
    - description: 'C++ with header in include subdir'
    - allow: 'widget\.cpp'
      companion:
        - require: 'include/'
        - require: 'include/gadget.h'
directory_map:
    /:
    - description: 'Root directory'
    - use_rule: cpp_with_header_in_include
"""
    flags = Flags()
    flags.verbose = True
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config, flags)

    assert len(errors) == 0
    assert len(warnings) == 0


def test_companion_with_template_parameters(tmp_path):
    """Test that companions can use both template parameters and capture groups."""
    repo = create_repo_structure(
        tmp_path,
        """
controller.py
controller_test.py
service.rs
service_test.rs
utils.cpp
utils_test.cpp
""",
    )
    config_yaml = r"""
templates:
    module_with_test:
        - description: 'Module with test file using template extension'
        - allow: '.*_test\.{{ext}}'
        - allow: '(?P<name>.*)\.{{ext}}'
          companion:
            - require: '{{name}}_test\.{{ext}}'
directory_map:
    /:
        - description: 'Root directory with multiple file types'
        - use_template: module_with_test
          parameters:
            ext: ['py', 'rs', 'cpp']
"""
    flags = Flags()
    flags.verbose = True
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config, flags)

    assert len(errors) == 0
    assert len(warnings) == 0


def test_companion_capture_with_regex_metacharacters(tmp_path):
    """Regression: a capture holding regex metacharacters matches literally.

    Before captures were passed through ``re.escape``, the expanded companion
    pattern for ``foo+bar.cpp`` was ``foo+bar\\.h``, which does not match the
    literal file ``foo+bar.h`` — a false 'missing companion' error.
    """
    repo = create_repo_structure(
        tmp_path,
        """
foo+bar.cpp
foo+bar.h
""",
    )
    config_yaml = r"""
structure_rules:
  cpp_with_headers:
    - description: 'C++ files with required headers'
    - allow: '(?P<base>.*)\.cpp'
      companion:
        - require: '{{base}}\.h'
    - allow: '.*\.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_headers
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, warnings = _check_repo_directory_structure(repo, config)

    assert len(errors) == 0
    assert len(warnings) == 0


def test_companion_capture_metacharacters_do_not_match_loosely(tmp_path):
    """Regression: an escaped capture must not match regex-wise.

    Unescaped, ``foo+bar\\.h`` would happily match ``fooobar.h`` and hide the
    fact that the real companion ``foo+bar.h`` is missing.
    """
    repo = create_repo_structure(
        tmp_path,
        """
foo+bar.cpp
fooobar.h
""",
    )
    config_yaml = r"""
structure_rules:
  cpp_with_headers:
    - description: 'C++ files with required headers'
    - allow: '(?P<base>.*)\.cpp'
      companion:
        - require: '{{base}}\.h'
    - allow: '.*\.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_headers
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)

    companion_errors = [e for e in errors if e.code == "missing_companion"]
    assert len(companion_errors) == 1
    assert companion_errors[0].path == "foo+bar.cpp"


def test_companion_capture_with_unbalanced_parenthesis(tmp_path):
    """Regression: a capture that used to break regex compilation still checks.

    ``foo(bar`` substituted raw produced an uncompilable pattern whose
    ``re.error`` was swallowed, silently dropping the companion requirement.
    """
    repo = create_repo_structure(
        tmp_path,
        """
foo(bar.cpp
""",
    )
    config_yaml = r"""
structure_rules:
  cpp_with_headers:
    - description: 'C++ files with required headers'
    - allow: '(?P<base>.*)\.cpp'
      companion:
        - require: '{{base}}\.h'
    - allow: '.*\.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_headers
"""
    config = Configuration.from_yaml_string(config_yaml)
    errors, _ = _check_repo_directory_structure(repo, config)

    companion_errors = [e for e in errors if e.code == "missing_companion"]
    assert len(companion_errors) == 1
    assert companion_errors[0].path == "foo(bar.cpp"
    assert r"foo\(bar\.h" in companion_errors[0].message


def test_configuration_reused_across_scans(tmp_path):
    """Regression: scan counters must not leak back into the Configuration.

    Scanning a satisfying repository used to bump ``count`` on the shared
    ``RepoEntry`` objects, so a later scan of a repository that is missing the
    required file saw a stale non-zero count and reported no error.
    """
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure requiring a README'
    - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
"""
    config = Configuration.from_yaml_string(config_yaml)

    complete_repo = create_repo_structure(
        tmp_path / "complete",
        """
README.md
""",
    )
    incomplete_repo = create_repo_structure(tmp_path / "incomplete", "")

    errors, _ = _check_repo_directory_structure(complete_repo, config)
    assert len(errors) == 0

    errors, _ = _check_repo_directory_structure(incomplete_repo, config)
    assert [e.code for e in errors] == ["missing_required_entries"]
    assert "README" in errors[0].message

    # And the third scan of the complete repository still passes, proving the
    # incomplete scan did not leave state behind either.
    errors, _ = _check_repo_directory_structure(complete_repo, config)
    assert len(errors) == 0


def test_configuration_structure_rules_unmutated_by_scan(tmp_path):
    """Regression: scanning leaves ``Configuration.structure_rules`` counts at 0."""
    config_yaml = r"""
structure_rules:
  base_structure:
    - description: 'Base structure requiring a README'
    - require: 'README\.md'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
"""
    config = Configuration.from_yaml_string(config_yaml)
    repo = create_repo_structure(
        tmp_path,
        """
README.md
""",
    )

    _check_repo_directory_structure(repo, config)

    assert all(
        entry.count == 0
        for entries in config.structure_rules.values()
        for entry in entries
    )
