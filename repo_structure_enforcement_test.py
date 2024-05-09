# pylint: disable=import-error
"""Tests for repo_structure library functions."""
import os

import pytest
from repo_structure_config import Configuration
from repo_structure_enforcement import (
    MissingRequiredEntriesError,
    fail_if_invalid_repo_structure,
)


def chdir_test_tmpdir(func):
    """Change working directory to Bazel's TEST_TMPDIR."""

    def wrapper(*args, **kwargs):
        cwd = os.getcwd()
        os.chdir(os.environ.get("TEST_TMPDIR"))
        result = func(*args, **kwargs)
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


TEST_CONFIG_YAML = "test_config.yaml"


def test_missing_required_file():
    """Test missing required file."""
    specification = """
    doc/
    doc/software_component_name.techspec.md
    README.md
    main.py
"""
    _create_repo_directory_structure(specification)
    config = Configuration(TEST_CONFIG_YAML)
    with pytest.raises(MissingRequiredEntriesError):
        _assert_repo_directory_structure(config)


if __name__ == "__main__":
    pytest.main(["-s", "-v", __file__])
