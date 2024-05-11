# pylint: disable=import-error
"""Tests for repo_structure library functions."""
import os

import pytest
from repo_structure_config import Configuration, ConfigurationParseError
from repo_structure_enforcement import (
    MissingRequiredEntriesError,
    fail_if_invalid_repo_structure,
)


def chdir_test_tmpdir(func):
    """Change working directory to Bazel's TEST_TMPDIR."""

    def wrapper(*args, **kwargs):
        cwd = os.getcwd()
        os.chdir(os.environ.get("TEST_TMPDIR"))
        try:
            result = func(*args, **kwargs)
        finally:
            os.chdir(cwd)
        return result

    return wrapper


@chdir_test_tmpdir
def _create_repo_directory_structure(specification: str) -> None:
    """Creates a directory structure based on a specification file."""
    for item in iter(specification.splitlines()):
        if item.startswith("#") or item.strip() == "":
            continue
        if item.strip().endswith("/"):
            os.makedirs(item.strip(), exist_ok=True)
        else:
            with open(item.strip(), "w", encoding="utf-8") as f:
                f.write("Created for testing only")


@chdir_test_tmpdir
def _assert_repo_directory_structure(config: Configuration) -> None:
    fail_if_invalid_repo_structure(os.environ.get("TEST_TMPDIR"), config)


def test_all_empty():
    """Test empty directory structure and spec."""
    specification = """
"""
    config_yaml = r"""
"""
    _create_repo_directory_structure(specification)
    with pytest.raises(ConfigurationParseError):
        Configuration(config_yaml, True)


def test_missing_required_file():
    """Test missing required file."""
    specification = """
README.md
"""
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
    _create_repo_directory_structure(specification)
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


def test_missing_required_dir():
    """Test missing required directory."""
    specification = """
README.md
LICENSE
"""
    config_yaml = r"""
structure_rules:
  base_structure:
    files:
      - name: "LICENSE"
        mode: required
      - name: "README.md"
    dirs:
      - name: "python"
directory_mappings:
  /:
    - use_rule: base_structure
        """
    _create_repo_directory_structure(specification)
    config = Configuration(config_yaml, True)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


if __name__ == "__main__":
    pytest.main(["-s", "-v", __file__])
