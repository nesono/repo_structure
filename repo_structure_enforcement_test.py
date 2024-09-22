# pylint: disable=import-error
"""Tests for repo_structure library functions."""
import os
import sys
from typing import Optional

import pytest
from repo_structure_config import Configuration, ConfigurationParseError
from repo_structure_enforcement import (
    MissingMappingError,
    MissingRequiredEntriesError,
    UnspecifiedEntryError,
    fail_if_invalid_repo_structure,
    Flags,
)


def chdir_test_tmpdir(func):
    """Change working directory to Bazel's TEST_TMPDIR. Use as decorator"""

    def wrapper(*args, **kwargs):
        cwd = os.getcwd()
        os.chdir(os.environ.get("TEST_TMPDIR"))
        try:
            result = func(*args, **kwargs)
        finally:
            os.chdir(cwd)
        return result

    return wrapper


def with_repo_structure(specification: str):
    """Create and remove repo structure based on specification for testing. Us as decorator."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            _create_repo_directory_structure(specification)
            try:
                result = func(*args, **kwargs)
            finally:
                _clear_repo_directory_structure()
            return result

        return wrapper

    return decorator


@chdir_test_tmpdir
def _create_repo_directory_structure(specification: str) -> None:
    """Creates a directory structure based on a specification file.

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


@chdir_test_tmpdir
def _clear_repo_directory_structure() -> None:
    for root, dirs, files in os.walk(os.environ.get("TEST_TMPDIR", ""), topdown=False):
        if not root:
            continue
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))


@chdir_test_tmpdir
def _assert_repo_directory_structure(
    config: Configuration, flags: Optional[Flags] = None
) -> None:
    if flags is None:
        flags = Flags()
    repo_root = os.environ.get("TEST_TMPDIR")
    assert repo_root is not None
    try:
        fail_if_invalid_repo_structure(repo_root, config, flags)
    finally:
        _clear_repo_directory_structure()


@with_repo_structure("")
def test_all_empty():
    """Test empty directory structure and spec."""
    config_yaml = r"""
"""
    with pytest.raises(ConfigurationParseError):
        Configuration(config_yaml, True)


@with_repo_structure(
    """
README.md
"""
)
def test_matching_regex():
    """Test with required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: '.*\.md'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


@with_repo_structure(
    """
README.md
LICENSE
python/
python/main.py
"""
)
def test_required_dir():
    """Test with required directory."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: "LICENSE"
        mode: required
      - name: "README.md"
    dirs:
      - name: "python"
        files:
            - name: '[^/]*'
directory_mappings:
  /:
    - use_rule: base_structure
        """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


@with_repo_structure(
    """
README.md
LICENSE
python/
python/main.py
unspecified/
"""
)
def test_unspecified_dir():
    """Test with required directory."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: "LICENSE"
        mode: required
      - name: "README.md"
    dirs:
      - name: "python"
        files:
            - name: '.*'
directory_mappings:
  /:
    - use_rule: base_structure
        """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
README.md
"""
)
def test_missing_root_mapping():
    """Test missing root mapping."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: "LICENSE"
        mode: required
      - name: "README.md"
        # mode: required is default
directory_mappings:
  /some_dir:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingMappingError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
README.md
"""
)
def test_missing_required_file():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: "LICENSE"
        mode: required
      - name: "README.md"
        # mode: required is default
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
README.md
LICENSE
"""
)
def test_missing_required_dir():
    """Test missing required directory."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: "LICENSE"
        mode: required
      - name: "README.md"
    dirs:
      - name: "python"
        files:
            - name: '.*'
directory_mappings:
  /:
    - use_rule: base_structure
        """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
README.md
main.py
"""
)
def test_multi_use_rule():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: README.md
  python_package:
    files:
      - name: '.*\.py'
        mode: required
directory_mappings:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


@with_repo_structure(
    """
main.py
"""
)
def test_multi_use_rule_missing_readme():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: README.md
  python_package:
    files:
      - name: '.*\.py'
        mode: required
directory_mappings:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
README.md
"""
)
def test_multi_use_rule_missing_py_file():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: README.md
  python_package:
    files:
      - name: '.*\.py'
        mode: required
directory_mappings:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
filename.txt
dirname/
"""
)
def test_conflicting_file_and_dir_names():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: '.*name.*'
    dirs:
      - name: '.*name.*'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


@with_repo_structure(
    """
dirname/
"""
)
def test_conflicting_dir_name():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: '.*name.*'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
filename.txt
"""
)
def test_conflicting_file_name():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    dirs:
      - name: '.*name.*'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
filename.txt
"""
)
def test_filename_with_bad_substring_match():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: '.*name'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
main.py
README.md
lib/
lib/lib.py
"""
)
def test_use_rule_recursive():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: README.md
  python_package:
    files:
      - name: '[^/]*\.py'
        mode: required
    dirs:
      - name: '.*'
        mode: optional
        use_rule: python_package
directory_mappings:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


@with_repo_structure(
    """
main.py
README.md
lib/
lib/README.md
"""
)
def test_fail_use_rule_recursive():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: README.md
  python_package:
    files:
      - name: '[^/]*\.py'
        mode: required
    dirs:
      - name: '[^/]*'
        mode: optional
        use_rule: python_package
directory_mappings:
  /:
    - use_rule: base_structure
    - use_rule: python_package
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
    """
main.py
README.md
lib/
lib/README.md
"""
)
def test_fail_directory_mapping_precedence():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: README.md
  python_package:
    files:
      - name: '[^/]*\.py'
        mode: required
    dirs:
      - name: '[^/]*'
        mode: optional
        use_rule: python_package
directory_mappings:
  /:
    - use_rule: base_structure
    - use_rule: python_package
  /lib/:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


@with_repo_structure(
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
def test_elaborate_use_rule_recursive():
    """Test missing required file."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: README.md
    dirs:
      - name: app
        mode: optional
  python_package:
    files:
      - name: '[^/]*\.py'
        mode: required
    dirs:
      - name: '.*'
        mode: optional
        use_rule: python_package
directory_mappings:
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


@with_repo_structure(
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
    files:
      - name: 'README.md'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


@with_repo_structure(
    """
README.md
"""
)
def test_fail_hidden_file_required_despite_hidden_disabled():
    """Test missing required hidden file - hidden files not tracked."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: '\.hidden.md'
      - name: 'README.md'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


@with_repo_structure(
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
    files:
      - name: '\.hidden.md'
      - name: 'README.md'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.include_hidden = True
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config, flags)


@with_repo_structure(
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
    files:
      - name: 'README.md'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    _assert_repo_directory_structure(config)


@with_repo_structure(
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
    files:
      - name: 'README.md'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.follow_symlinks = True
    with pytest.raises(UnspecifiedEntryError):
        _assert_repo_directory_structure(config, flags)


@with_repo_structure(
    """
README.md
link -> README.md
"""
)
def test_succeed_specified_link():
    """Test for unspecified symlink."""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: 'README.md'
      - name: 'link'
directory_mappings:
  /:
    - use_rule: base_structure
    """
    config = Configuration(config_yaml, True)
    flags = Flags()
    flags.follow_symlinks = True
    _assert_repo_directory_structure(config, flags)


if __name__ == "__main__":
    sys.exit(pytest.main(["-s", "-v", __file__]))
