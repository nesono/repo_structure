"""Main tests module."""

from pathlib import Path

import click
from click.testing import CliRunner
from .__main__ import repo_structure
from .report import FORMATTERS

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = str(_PACKAGE_DIR.parent)
"""These tests drive the CLI against this repository itself, so they anchor on
the package directory rather than on the process CWD."""


def _config(name: str) -> str:
    """Absolute path of a configuration fixture living beside this module."""
    return str(_PACKAGE_DIR / name)


def test_main_full_scan_success():
    """Test successful main run."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "--verbose",
            "full-scan",
            "-r",
            _REPO_ROOT,
            "-c",
            _config("test_config_allow_all.yaml"),
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
            _REPO_ROOT,
            "-c",
            _config("test_config_bad_config.yaml"),
        ],
    )

    assert result.exit_code != 0


def test_main_full_scan_fail_bad_pattern(tmp_path):
    """Test that an uncompilable pattern is reported, not raised as a traceback."""
    config_path = tmp_path / "bad_pattern.yaml"
    config_path.write_text(
        """
structure_rules:
  bad_pattern_rule:
    - description: "Rule with an uncompilable pattern"
    - require: "[unclosed"

directory_map:
  /:
    - description: "Root directory"
    - use_rule: bad_pattern_rule
""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        ["full-scan", "-r", _REPO_ROOT, "-c", str(config_path)],
    )

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "failed to compile" in result.output


def test_main_full_scan_fail():
    """Test failing main run due to missing file."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        ["full-scan", "-r", _REPO_ROOT, "-c", _config("test_config_fail.yaml")],
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
            _config("test_config_allow_all.yaml"),
            "LICENSE",
            "repo_structure.yaml",
            "repo_structure/config.py",
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
            _config("test_config_bad_config.yaml"),
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
            _config("test_config_fail.yaml"),
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
            _config("test_config_fail.yaml"),
            "/etc/passwd",
        ],
    )

    assert "/etc/passwd" in result.output
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
            _REPO_ROOT,
            "-c",
            _config("test_config_allow_all.yaml"),
        ],
    )

    assert result.exit_code == 0


def test_main_include_hidden_default():
    """Test main command with default include-hidden behavior."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan",
            "-r",
            _REPO_ROOT,
            "-c",
            _config("test_config_allow_all.yaml"),
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
            _config("test_config_allow_all.yaml"),
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
            _config("test_config_fail.yaml"),
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


def test_main_full_scan_with_warnings():
    """Test full_scan command that generates warnings."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan",
            "-r",
            _REPO_ROOT,
            "-c",
            _config("test_config_with_warnings.yaml"),
        ],
    )

    # Test succeeds if we see warnings output (may also have errors causing exit 1)
    assert "Warnings:" in result.output
    assert "unused_rule" in result.output


def test_main_full_scan_directory_success():
    """Test full_scan command on a specific directory."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan",
            "-r",
            _REPO_ROOT,
            "-c",
            _config("test_config_allow_all.yaml"),
            "-d",
            "repo_structure",
        ],
    )
    assert "repo_structure" in result.output
    assert result.exit_code == 0


def test_main_full_scan_directory_fail():
    """Test full_scan command on a specific directory."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "full-scan",
            "-r",
            _REPO_ROOT,
            "-c",
            _config("test_config_allow_all.yaml"),
            "-d",
            "bad_directory",
        ],
    )
    assert result.exit_code != 0


def test_report_command_text():
    """Test report command with text output."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "report",
            "-c",
            _config("test_config_allow_all.yaml"),
            "-f",
            "text",
        ],
    )

    assert result.exit_code == 0
    assert "Repository Structure Configuration Report" in result.output


def test_report_command_json():
    """Test report command with JSON output."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "report",
            "-c",
            _config("test_config_allow_all.yaml"),
            "-f",
            "json",
        ],
    )

    assert result.exit_code == 0


def test_report_command_markdown():
    """Test report command with Markdown output."""
    runner = CliRunner()
    result = runner.invoke(
        repo_structure,
        [
            "report",
            "-c",
            _config("test_config_allow_all.yaml"),
            "-f",
            "markdown",
        ],
    )

    assert result.exit_code == 0
    assert "# Repository Structure Configuration Report" in result.output


def test_report_command_help():
    """Test report help command."""
    runner = CliRunner()
    result = runner.invoke(repo_structure, ["report", "--help"])

    assert result.exit_code == 0
    assert "Generate a report of the configuration structure" in result.output


def test_report_output_format_choices_match_registry():
    """The CLI offers exactly the formats registered in FORMATTERS."""
    report_command = repo_structure.commands["report"]
    output_format = next(
        param for param in report_command.params if param.name == "output_format"
    )

    assert isinstance(output_format.type, click.Choice)
    assert list(output_format.type.choices) == list(FORMATTERS)
