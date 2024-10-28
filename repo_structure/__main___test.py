# pylint: disable=import-error
"""Main tests module."""
from click.testing import CliRunner
from .__main__ import repo_structure_main


def test_main_check_all_success():
    """Test successful main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure_main,
        [
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
            "--check-all",
            "--verbose",
        ],
    )

    assert result.exit_code == 0


def test_main_check_all_fail():
    """Test failing main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure_main,
        ["-r", ".", "-c", "repo_structure/test_config_fail.yaml", "--check-all"],
    )

    assert result.exit_code != 0


def test_main_check_path_success():
    """Test successful main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure_main,
        [
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
            "--verbose",
            "repo_structure/repo_structure_config.py",
        ],
    )

    assert result.exit_code == 0


def test_main_check_path_fail():
    """Test failing main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure_main,
        [
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_fail.yaml",
            "BADFILE",
        ],
    )

    assert result.exit_code != 0
