# pylint: disable=import-error
"""Main tests module."""
from click.testing import CliRunner
from .__main__ import repo_structure


def test_main_full_scan_success():
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


def test_main_full_scan_fail_bad_config():
    """Test failing main run due to bad configuration file."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_bad_config.yaml",
        ],
    )

    assert result.exit_code != 0


def test_main_full_scan_fail():
    """Test failing main run due to missing file."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        ["full-scan", "-r", ".", "-c", "repo_structure/test_config_fail.yaml"],
    )

    assert result.exit_code != 0


def test_main_diff_scan_success():
    """Test successful main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "--verbose",
            "diff-scan",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
            "LICENSE",
            "repo_structure.yaml",
            "repo_structure/repo_structure_config.py",
        ],
    )

    assert result.exit_code == 0


def test_main_diff_scan_fail_bad_config():
    """Test failing main run due to bad config."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "diff-scan",
            "-c",
            "repo_structure/test_config_bad_config.yaml",
            "LICENSE",
        ],
    )

    assert "bad_rule" in result.output
    assert result.exit_code != 0


def test_main_diff_scan_fail():
    """Test failing main run due to bad file."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "diff-scan",
            "-c",
            "repo_structure/test_config_fail.yaml",
            "LICENSE",
        ],
    )

    assert "LICENSE" in result.output
    assert result.exit_code != 0


def test_main_diff_scan_fail_abs_path():
    """Test failing main run due to bad file."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "diff-scan",
            "-c",
            "repo_structure/test_config_fail.yaml",
            "/etc/passwd",
        ],
    )

    assert "/etc/passwd" in result.output
    assert result.exit_code != 0
