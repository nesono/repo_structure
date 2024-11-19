# pylint: disable=import-error
# pylint: disable=duplicate-code
# pylint: disable=too-many-lines
"""Tests for repo_structure library functions."""
import os
import shutil
import tempfile
from typing import Callable, TypeVar

import pytest

from .repo_structure_config import Configuration
from .repo_structure_full_scan import (
    MissingMappingError,
    MissingRequiredEntriesError,
    assert_full_repository_structure,
)
from .repo_structure_lib import (
    Flags,
    UnspecifiedEntryError,
    ConfigurationParseError,
    ForbiddenEntryError,
)


def _get_tmp_dir() -> str:
    return tempfile.mkdtemp()


def _remove_tmp_dir(tmpdir: str) -> None:
    shutil.rmtree(tmpdir)


def _create_repo_directory_structure(specification: str) -> None:
    """Creates a directory structure based on a specification file.
    Must be run in the target directory.

    A specification file can contain the following entries:
    | Entry                      | Meaning                                                         |
    | # <string>                 | comment string (ignored in output)                              |
    | <filename>:<content>       | File with content <content> (single line only)                  |
    | <dirname>/                 | Directory                                                       |
    | <linkname> -> <targetfile> | Symbolic link with the name <linkname> pointing to <targetfile> |
    """
    for item in iter(specification.splitlines()):
        if item.startswith("#") or item.strip() == "":
            continue
        if item.strip().endswith("/"):
            os.makedirs(item.strip(), exist_ok=True)
        elif "->" in item:
            link_name, target_file = item.strip().split("->")
            os.symlink(target_file.strip(), link_name.strip())
        else:
            file_content = "Created for testing only"
            if ":" in item:
                file_name, file_content = item.strip().split(":")
            else:
                file_name = item.strip()
            with open(file_name.strip(), "w", encoding="utf-8") as f:
                f.write(file_content.strip() + "\r\n")


def _clear_repo_directory_structure() -> None:
    for root, dirs, files in os.walk(".", topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))


R = TypeVar("R")


def with_repo_structure_in_tmpdir(specification: str):
    """Create and remove repo structure based on specification for testing. Use as decorator."""

    def decorator(func: Callable[..., R]) -> Callable[..., R]:

        def wrapper(*args, **kwargs):
            cwd = os.getcwd()
            tmpdir = _get_tmp_dir()
            os.chdir(tmpdir)
            _create_repo_directory_structure(specification)
            try:
                result = func(*args, **kwargs)
            finally:
                _clear_repo_directory_structure()
                os.chdir(cwd)
                _remove_tmp_dir(tmpdir)
            return result

        return wrapper

    return decorator


def _assert_repo_directory_structure(
    config: Configuration,
    flags: Flags = Flags(),
) -> None:
    assert_full_repository_structure(".", config, flags)


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
    - require: '.*\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: 'python/'
      if_exists:
      - allow: '.*\.py'
directory_map:
  /:
    - use_rule: base_structure
        """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: "README.md"
    - require: "python/"
      if_exists:
      - require: '.*'
directory_map:
  /:
    - use_rule: base_structure
        """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


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
      - require: "irrelevant"
directory_map:
  /some_dir/:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingMappingError):
        _assert_repo_directory_structure(config)


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
    - require: "LICENSE"
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


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
    - require: 'README\.md'
    - require: 'python/'
      if_exists:
      - require: '.*'
directory_map:
  /:
    - use_rule: base_structure
        """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


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
    - require: '.*'
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
"""
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


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
      - require: 'README\.md'
  python_package:
      - require: '.*\.py'
directory_map:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
      - require: 'README\.md'
  python_package:
      - require: '.*\.py'
directory_map:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


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
      - require: '.*name.*'
      - require: '.*name.*/'
        if_exists:
        - allow: '.*'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: '.*name.*'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


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
    - require: '.*name.*/'
      if_exists:
      - allow: '.*'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


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
    - require: '.*name'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


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
    - require: 'LICENSE'
    - allow: 'doc/'
      if_exists:
        - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: 'LICENSE'
    - allow: 'doc/'
      if_exists:
        - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


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
    - require: 'LICENSE'
    - allow: 'doc/'
      if_exists:
        - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: 'README\.md'
  python_package:
    - require: '.*\.py'
    - require: '.*/'
      use_rule: python_package
directory_map:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


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
    - require: 'README\.md'
  python_package:
    - require: '.*\.py'
    - allow: '.*/'
      use_rule: python_package
directory_map:
  /:
    - use_rule: base_structure
    - use_rule: python_package
  /lib/:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    _assert_repo_directory_structure(config)


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
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.include_hidden = False
    _assert_repo_directory_structure(config, flags)


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
     - require: '\.hidden\.md'
     - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.include_hidden = True
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


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
    - require: '\.hidden.md'
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.include_hidden = True
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config, flags)


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
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.follow_symlinks = True
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config, flags)


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
    - require: 'README\.md'
    - require: 'link'
directory_map:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.follow_symlinks = True
    _assert_repo_directory_structure(config, flags)


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
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
"""
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
"""
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


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
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - allow: 'doc/'
        if_exists:
          - require: '{{component}}.techspec.md'
directory_map:
  /:
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
"""
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
  /subdir/:
    - use_template: component
      parameters:
        component: ['control', 'camera']
"""
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - use_template: component
      parameters:
        component: ['lidar', 'driver']
  /subdir/:
    - use_template: component
      parameters:
        component: ['control', 'camera']
"""
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


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
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.{{extension}}'
      - require: 'doc/'
        if_exists:
        - require: '{{component}}.techspec.md'
directory_map:
  /:
    - use_template: example_template
      parameters:
        component: ['lidar', 'driver']
        extension: ['rs']
  /subdir/:
    - use_template: example_template
      parameters:
        component: ['control', 'camera']
        extension: ['py']
"""
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


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
    - require: 'README\.md'
    - allow: 'doc/'
      use_rule: base_structure
templates:
  component:
    - require: '{{component}}/'
      if_exists:
      - require: '{{component}}_component.py'
      - allow: 'doc/'
        if_exists:
          - require: '{{component}}.techspec.md'
          - forbid: 'CMakeLists\.txt'
directory_map:
  /:
    - use_template: component
      parameters:
        component: ['lidar']
    - use_rule: base_structure
"""
    flags = Flags()
    flags.verbose = True
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config, flags)


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
    - require: 'README\.md'
    - forbid: 'CMakeLists\.txt'
    - require: 'python/'
      if_exists:
      - require: '.*\.py'
directory_map:
  /:
    - use_rule: base_structure
        """
    config = Configuration(config_yaml, True)
    with pytest.raises(ForbiddenEntryError):
        _assert_repo_directory_structure(config)


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
    - require: 'README\.md'
directory_map:
  /:
    - use_rule: base_structure
  /python/:
    - use_rule: ignore
        """
    flags = Flags()
    flags.verbose = True
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config, flags)
