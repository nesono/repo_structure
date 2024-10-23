# pylint: disable=import-error
"""Main tests module."""

from click.testing import CliRunner
from repo_structure.__main__ import main


def test_main_success():
    """Test successful main run."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["-r", ".", "-c", "repo_structure/test_config_allow_all.yaml", "--verbose"],
    )

    assert result.exit_code == 0


def test_main_fail():
    """Test failing main run."""
    runner = CliRunner()
    result = runner.invoke(
        main, ["-r", ".", "-c", "repo_structure/test_config_fail.yaml"]
    )

    assert result.exit_code != 0
