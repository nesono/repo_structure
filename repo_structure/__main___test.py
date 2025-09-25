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


def test_main_full_scan_warning_success():
    """Test successful full_scan_warning command."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "--verbose",
            "full-scan-warning",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
        ],
    )

    assert result.exit_code == 0
    assert "Running full scan (non-throwing)" in result.output


def test_main_full_scan_warning_fail_bad_config():
    """Test failing full_scan_warning due to bad configuration file."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan-warning",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_bad_config.yaml",
        ],
    )

    assert result.exit_code != 0


def test_main_full_scan_warning_fail():
    """Test failing full_scan_warning due to missing file."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan-warning",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_fail.yaml",
        ],
    )

    assert result.exit_code != 0


def test_main_global_flags():
    """Test main command with global flags."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "--follow-symlinks",
            "--include-hidden",
            "--verbose",
            "full-scan",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
        ],
    )

    assert result.exit_code == 0
    assert "Repo-Structure started" in result.output


def test_main_include_hidden_default():
    """Test main command with default include-hidden behavior."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
        ],
    )

    assert result.exit_code == 0


def test_main_version():
    """Test version option."""
    runner = CliRunner()
    result = runner.invoke(repo_structure, ["--version"])

    assert result.exit_code == 0
    assert "Repo-Structure" in result.output


def test_main_diff_scan_empty_paths():
    """Test diff_scan with no paths provided."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "diff-scan",
            "-c",
            "repo_structure/test_config_allow_all.yaml",
        ],
    )

    assert result.exit_code == 0
    assert "Running diff scan" in result.output


def test_main_diff_scan_multiple_paths_with_failure():
    """Test diff_scan with multiple paths where some fail."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "diff-scan",
            "-c",
            "repo_structure/test_config_fail.yaml",
            "LICENSE",
            "repo_structure.yaml",
            "/absolute/path",
        ],
    )

    assert result.exit_code != 0
    assert "LICENSE" in result.output
    assert "/absolute/path" in result.output


def test_main_help():
    """Test help command."""
    runner = CliRunner()
    result = runner.invoke(repo_structure, ["--help"])

    assert result.exit_code == 0
    assert "Ensure clean repository structure" in result.output


def test_main_full_scan_help():
    """Test full-scan help command."""
    runner = CliRunner()
    result = runner.invoke(repo_structure, ["full-scan", "--help"])

    assert result.exit_code == 0
    assert "Run a full scan on all files" in result.output


def test_main_diff_scan_help():
    """Test diff-scan help command."""
    runner = CliRunner()
    result = runner.invoke(repo_structure, ["diff-scan", "--help"])

    assert result.exit_code == 0
    assert "Run a check on a differential set" in result.output


def test_main_full_scan_warning_help():
    """Test full-scan-warning help command."""
    runner = CliRunner()
    result = runner.invoke(repo_structure, ["full-scan-warning", "--help"])

    assert result.exit_code == 0
    assert "Run a full scan and print warnings" in result.output


def test_main_full_scan_with_warnings():
    """Test full_scan command that generates warnings."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_with_warnings.yaml",
        ],
    )

    # Test succeeds if we see warnings output (may also have errors causing exit 1)
    assert "Warnings:" in result.output
    assert "unused_rule" in result.output


def test_main_full_scan_warning_with_warnings():
    """Test full_scan_warning command that generates warnings."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan-warning",
            "-r",
            ".",
            "-c",
            "repo_structure/test_config_with_warnings.yaml",
        ],
    )

    # Test succeeds if we see warnings output (may also have errors causing exit 1)
    assert "Warnings:" in result.output
    assert "unused_rule" in result.output
