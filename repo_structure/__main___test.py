# pylint: disable=import-error
"""Main tests module."""
from click.testing import CliRunner
from .__main__ import repo_structure


def test_main_check_all_success():
    """Test successful main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "--verbose",
            "full-scan",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
        ],
    )

    assert result.exit_code == 0


def test_main_check_all_fail():
    """Test failing main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        ["full-scan", "-r", ".", "-c", "repo_structure/test_config_fail.yaml"],
    )

    assert result.exit_code != 0


def test_main_check_path_success():
    """Test successful main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "--verbose",
            "check-files",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
            "LICENSE",
            "repo_structure/repo_structure_config.py",
        ],
    )

    assert result.exit_code == 0


def test_main_check_path_fail():
    """Test failing main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "check-files",
            "-c",
            "repo_structure/test_config_fail.yaml",
            "BADFILE",
        ],
    )

    assert result.exit_code != 0
