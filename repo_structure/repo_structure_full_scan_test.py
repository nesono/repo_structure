# pylint: disable=duplicate-code
# pylint: disable=too-many-lines
"""Tests for repo_structure library functions."""

import pytest

from .repo_structure_config import Configuration
from .repo_structure_full_scan import (
    FullScanProcessor,
    ScanIssue,
)
from .repo_structure_lib import (
    Flags,
    ConfigurationParseError,
)

from .repo_structure_test_lib import with_repo_structure_in_tmpdir


def _check_repo_directory_structure(
    config: Configuration,
    flags: Flags = Flags(),
) -> tuple[list[ScanIssue], list[ScanIssue]]:
    """Check repository structure and return errors and warnings instead of asserting."""
    processor = FullScanProcessor(".", config, flags)
    return processor.scan()


@with_repo_structure_in_tmpdir("")
def test_all_empty():
    """Test empty directory structure and spec."""
    config_yaml = r"""
"""
    with pytest.raises(ConfigurationParseError):
        Configuration(config_yaml, True)


@with_repo_structure_in_tmpdir(
    """
README.md
"""
)
def test_matching_regex():
    """Test with required file."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
python/
python/main.py
"""
)
def test_required_dir():
    """Test with required directory."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
README.md
python/
python/main.py
unspecified/
"""
)
def test_unspecified_dir():
    """Test with unspecified directory in directory, where only files are allowed."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "unspecified_entry"
    assert "unspecified" in errors[0].path


@with_repo_structure_in_tmpdir(
    """
README.md
"""
)
def test_missing_root_mapping():
    """Test missing root mapping."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_root_mapping"


@with_repo_structure_in_tmpdir(
    """
README.md
"""
)
def test_missing_required_file():
    """Test missing required file."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


@with_repo_structure_in_tmpdir(
    """
README.md
"""
)
def test_missing_required_dir():
    """Test missing required directory."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


@with_repo_structure_in_tmpdir(
    """
README.md
"""
)
def test_fail_rule_precedence():
    """Test rule precedence. This needs to fail because the wildcard consumes all matches.

    The first match wins and thus the README.md will never be reached."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


@with_repo_structure_in_tmpdir(
    """
README.md
main.py
"""
)
def test_multi_use_rule():
    """Test using multiple rules."""
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
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
README.md
"""
)
def test_multi_use_rule_missing_py_file():
    """Test missing required pattern file while using multi rules."""
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
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


@with_repo_structure_in_tmpdir(
    """
filename.txt
dirname/
"""
)
def test_conflicting_file_and_dir_names():
    """Test two required entries, one file, one dir. Need to pass ensuring distinct detection."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
dirname/
"""
)
def test_conflicting_dir_name():
    """Ensure that a matching directory does not suffice a required file."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 2
    assert errors[0].code == "missing_required_entries"
    assert errors[1].code == "unspecified_entry"


@with_repo_structure_in_tmpdir(
    """
filename.txt
"""
)
def test_conflicting_file_name():
    """Ensure that a matching file does not suffice a required directory."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 2
    assert errors[0].code == "missing_required_entries"
    assert errors[1].code == "unspecified_entry"


@with_repo_structure_in_tmpdir(
    """
filename.txt
"""
)
def test_filename_with_bad_substring_match():
    """Ensure substring match is not enough to match."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 2
    assert errors[0].code == "missing_required_entries"
    assert errors[1].code == "unspecified_entry"


@with_repo_structure_in_tmpdir(
    """
LICENSE
"""
)
def test_required_file_in_optional_directory_no_entry():
    """Test required file under optional directory - no entry."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
LICENSE
doc/
"""
)
def test_required_file_in_optional_directory_with_entry():
    """Test required file under optional directory - with directory entry."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


@with_repo_structure_in_tmpdir(
    """
LICENSE
doc/
doc/README.md
"""
)
def test_required_file_in_optional_directory_with_entry_and_exists():
    """Test required file under optional directory - with directory entry and file."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
main.cpp
README.md
lib/
lib/lib.cpp
"""
)
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
main.py
README.md
lib/
lib/README.md
"""
)
def test_fail_use_rule_recursive():
    """Ensure use_rules are not mixed up in recursion."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 2
    assert errors[0].code == "missing_required_entries"
    assert errors[0].path == "lib"
    assert errors[1].code == "unspecified_entry"
    assert errors[1].path == "lib/README.md"


@with_repo_structure_in_tmpdir(
    """
main.py
README.md
lib/
lib/README.md
"""
)
def test_fail_directory_mapping_precedence():
    """Test that directories from directory_mapping take precedence."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
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
"""
)
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
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
.hidden.md
README.md
"""
)
def test_succeed_ignored_hidden_file():
    """Test existing ignored hidden file - hidden files not tracked."""
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
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.include_hidden = False
    errors, warnings = _check_repo_directory_structure(config, flags)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
README.md
"""
)
def test_fail_hidden_file_required_despite_hidden_disabled():
    """Test with a missing, required, hidden file - hidden files not tracked."""
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
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.include_hidden = True
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


@with_repo_structure_in_tmpdir(
    """
README.md
.hidden.md
.unspecified.md
"""
)
def test_fail_unspecified_hidden_files_when_hidden_enabled():
    """Test for unspecified hidden file - hidden files tracked."""
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
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.include_hidden = True
    errors, _ = _check_repo_directory_structure(config, flags)
    assert len(errors) == 1
    assert errors[0].code == "unspecified_entry"


@with_repo_structure_in_tmpdir(
    """
README.md
ignored.md
.gitignore:ignored.md
"""
)
def test_succeed_gitignored_file():
    """Test for ignored file from gitignore."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
README.md
link -> README.md
"""
)
def test_fail_unspecified_link():
    """Test for unspecified symlink."""
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
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.follow_symlinks = True
    errors, warnings = _check_repo_directory_structure(config, flags)
    assert len(errors) == 1
    assert errors[0].code == "unspecified_entry"
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
README.md
link -> README.md
"""
)
def test_succeed_specified_link():
    """Test for specified symlink."""
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
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.follow_symlinks = True
    errors, warnings = _check_repo_directory_structure(config, flags)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/doc/
driver/doc/driver.techspec.md
"""
)
def test_succeed_template_rule():
    """Test template with single parameter."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/doc/
"""
)
def test_fail_template_rule_missing_file():
    """Test template with single parameter missing file."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


@with_repo_structure_in_tmpdir(
    """
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/
"""
)
def test_succeed_template_rule_if_exists():
    """Test template with if_exists clause and optional dir missing."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
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
"""
)
def test_succeed_template_rule_subdirectory_map():
    """Test template with single parameter and subdirectory map."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
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
"""
)
def test_fail_template_rule_subdirectory_map_missing_file():
    """Test template with single parameter and subdirectory map missing file."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "missing_required_entries"


@with_repo_structure_in_tmpdir(
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
"""
)
def test_succeed_template_rule_multiple_expansions():
    """Test template with single parameter and subdirectory map."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
README.md
link_to_skip -> README.md
doc/
doc/README.md
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
"""
)
def test_succeed_with_verbose():
    """Test enforcement with verbose flag enabled."""
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
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config, flags)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
README.md
CMakeLists.txt
python/
python/main.py
"""
)
def test_forbid_file():
    """Test with required directory."""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)
    assert len(errors) == 1
    assert errors[0].code == "forbidden_entry"


@with_repo_structure_in_tmpdir(
    """
README.md
python/
python/whatever.py
python/this_is_ignored.py
"""
)
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
    flags = Flags()
    flags.verbose = True
    config = Configuration(config_yaml, True)
    errors, warnings = _check_repo_directory_structure(config, flags)
    assert len(errors) == 0
    assert len(warnings) == 0


@with_repo_structure_in_tmpdir(
    """
README.md
"""
)
def test_warn_on_unused_structure_rule():  # pylint: disable=import-outside-toplevel
    """Warn if a structure rule exists in the configuration but is never used in the scan.

    Using the non-throwing API, warnings are returned as ScanIssue entries.
    """
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
    config = Configuration(config_yaml, True)
    processor = FullScanProcessor(".", config, Flags())
    _, warnings = processor.scan()
    assert any(
        "unused_rule" in i.message for i in warnings
    ), f"Expected unused rule warning, got: {warnings}"


@with_repo_structure_in_tmpdir(
    """
widget.cpp
widget.h
engine.cpp
"""
)
def test_requires_companion_full_scan():
    """Test that full scan detects missing companion files."""
    config_yaml = r"""
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
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)

    # Should have error for engine.cpp missing engine.h
    assert len(errors) == 1
    assert errors[0].path == "engine.cpp"
    assert "engine.h" in errors[0].message
    assert "Missing required companion" in errors[0].message
    assert errors[0].code == "missing_companion"


@with_repo_structure_in_tmpdir(
    """
widget.cpp
widget.h
include/
include/engine.h
engine.cpp
"""
)
def test_requires_companion_subdirectory_full_scan():
    """Test that full scan detects missing companions in subdirectories."""
    config_yaml = r"""
structure_rules:
  cpp_with_header_in_include:
    - description: 'C++ with header in include subdir'
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: 'include/{{base}}.h'
    - allow: '.*\.cpp'
    - allow: '.*\.h'
    - allow: 'include/'
      if_exists:
        - allow: '.*\.h'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_header_in_include
"""
    config = Configuration(config_yaml, True)
    errors, _ = _check_repo_directory_structure(config)

    # Should have error for widget.cpp missing include/widget.h companion
    assert len(errors) == 1
    assert errors[0].path == "widget.cpp"
    assert "include/widget.h" in errors[0].message
    assert errors[0].code == "missing_companion"
