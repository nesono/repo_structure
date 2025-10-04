"""Tests for repo_structure report functionality."""

import tempfile
import os
import subprocess
from pathlib import Path

from .repo_structure_config import Configuration
from .repo_structure_report import (
    generate_report,
    format_report_text,
    format_report_json,
    format_report_markdown,
    format_report,
    get_repository_info,
)


def test_generate_report_basic():
    """Test basic report generation with simple configuration."""
    test_yaml = """
structure_rules:
  basic_rule:
    - description: 'Basic rule for documentation'
    - require: 'README\\.md'
    - allow: '.*\\.txt'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    assert report.total_directories == 1
    assert report.total_structure_rules == 1
    assert len(report.directory_reports) == 1
    assert len(report.structure_rule_reports) == 1

    # Check directory report
    dir_report = report.directory_reports[0]
    assert dir_report.directory == "/"
    assert dir_report.description == "Root directory"
    assert dir_report.applied_rules == ["basic_rule"]

    # Check structure rule report
    rule_report = report.structure_rule_reports[0]
    assert rule_report.rule_name == "basic_rule"
    assert rule_report.description == "Basic rule for documentation"
    assert rule_report.applied_directories == ["/"]
    assert rule_report.rule_count == 2


def test_generate_report_with_descriptions():
    """Test report generation with description fields."""
    test_yaml = """
structure_rules:
  basic_rule:
    - description: 'Basic rule for documentation'
    - require: 'README\\.md'
    - allow: '.*\\.txt'
  python_rule:
    - description: 'Python package rule'
    - require: '__init__\\.py'
    - require: '.*\\.py'

structure_rule_descriptions:
  basic_rule: "Basic documentation and text files"
  python_rule: "Standard Python package structure"

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule
  /src/:
    - description: 'Source directory'
    - use_rule: python_rule

directory_descriptions:
  /: "Root directory with documentation"
  /src/: "Source code directory"
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    assert report.total_directories == 2
    assert report.total_structure_rules == 2

    # Check directory descriptions are included (inline takes precedence over description sections)
    root_dir = next(d for d in report.directory_reports if d.directory == "/")
    assert root_dir.description == "Root directory"

    src_dir = next(d for d in report.directory_reports if d.directory == "/src/")
    assert src_dir.description == "Source directory"

    # Check structure rule descriptions are included (inline takes precedence)
    basic_rule = next(
        r for r in report.structure_rule_reports if r.rule_name == "basic_rule"
    )
    assert basic_rule.description == "Basic rule for documentation"

    python_rule = next(
        r for r in report.structure_rule_reports if r.rule_name == "python_rule"
    )
    assert python_rule.description == "Python package rule"


def test_format_report_text():
    """Test text formatting of report."""
    test_yaml = """
structure_rules:
  basic_rule:
    - description: 'Basic rule for documentation'
    - require: 'README\\.md'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule

structure_rule_descriptions:
  basic_rule: "Basic rule description"

directory_descriptions:
  /: "Root directory description"
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)
    text_output = format_report_text(report)

    assert "Repository Structure Configuration Report" in text_output
    assert "Directory: /" in text_output
    assert "Root directory" in text_output
    assert "Rule: basic_rule" in text_output
    assert "Basic rule for documentation" in text_output


def test_format_report_json():
    """Test JSON formatting of report."""
    test_yaml = """
structure_rules:
  basic_rule:
    - description: 'Basic rule for documentation'
    - require: 'README\\.md'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)
    json_output = format_report_json(report)

    assert '"total_directories": 1' in json_output
    assert '"total_structure_rules": 1' in json_output
    assert '"directory": "/"' in json_output
    assert '"rule_name": "basic_rule"' in json_output


def test_format_report_markdown():
    """Test Markdown formatting of report."""
    test_yaml = """
structure_rules:
  basic_rule:
    - description: 'Basic rule for documentation'
    - require: 'README\\.md'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule

structure_rule_descriptions:
  basic_rule: "Basic rule description"
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)
    markdown_output = format_report_markdown(report)

    assert "# Repository Structure Configuration Report" in markdown_output
    assert "### Directory: `/`" in markdown_output
    assert "### Rule: `basic_rule`" in markdown_output
    assert "Basic rule for documentation" in markdown_output


def test_format_report_function():
    """Test the format_report function with different formats."""
    test_yaml = """
structure_rules:
  basic_rule:
    - description: 'Basic rule for documentation'
    - require: 'README\\.md'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    # Test text format (default)
    text_output = format_report(report)
    assert "Repository Structure Configuration Report" in text_output

    # Test explicit text format
    text_output_explicit = format_report(report, "text")
    assert text_output == text_output_explicit

    # Test JSON format
    json_output = format_report(report, "json")
    assert '"total_directories": 1' in json_output

    # Test Markdown format
    markdown_output = format_report(report, "markdown")
    assert "# Repository Structure Configuration Report" in markdown_output


def test_multiple_rules_per_directory():
    """Test report generation with multiple rules applied to a directory."""
    test_yaml = """
structure_rules:
  rule1:
    - description: 'Documentation rule'
    - require: 'README\\.md'
  rule2:
    - description: 'License rule'
    - require: 'LICENSE'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: rule1
    - use_rule: rule2

structure_rule_descriptions:
  rule1: "Documentation rule"
  rule2: "License rule"
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    dir_report = report.directory_reports[0]
    assert dir_report.applied_rules == ["rule1", "rule2"]
    assert dir_report.rule_descriptions == ["Documentation rule", "License rule"]

    # Both rules should show they're applied to root
    for rule_report in report.structure_rule_reports:
        assert "/" in rule_report.applied_directories


def test_empty_configuration():
    """Test report generation with minimal configuration."""
    test_yaml = """
structure_rules:
  dummy_rule:
    - description: 'Dummy rule'
    - allow: '.*'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: ignore
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    assert report.total_directories == 1
    assert report.total_structure_rules == 2  # dummy_rule and ignore are counted
    assert len(report.directory_reports) == 1
    assert len(report.structure_rule_reports) == 2  # dummy_rule and ignore

    dir_report = report.directory_reports[0]
    assert dir_report.directory == "/"
    assert dir_report.applied_rules == ["ignore"]
    assert dir_report.rule_descriptions == [
        "Builtin rule: Excludes this directory from structure validation"
    ]

    # Check that ignore rule has its own section
    ignore_rule = next(
        r for r in report.structure_rule_reports if r.rule_name == "ignore"
    )
    assert (
        ignore_rule.description
        == "Builtin rule: Excludes this directory from structure validation"
    )
    assert ignore_rule.rule_count == 0
    assert ignore_rule.patterns == []
    assert ignore_rule.applied_directories == ["/"]


def test_ignore_rule_description():
    """Test that the ignore builtin rule gets proper description in reports."""
    test_yaml = """
structure_rules:
  base_structure:
    - description: 'Base structure rule'
    - require: 'README\\.md'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: base_structure
  /.github/:
    - description: 'GitHub directory'
    - use_rule: ignore
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    # Find the .github directory report
    github_report = next(
        dr for dr in report.directory_reports if dr.directory == "/.github/"
    )

    assert github_report.applied_rules == ["ignore"]
    assert github_report.rule_descriptions == [
        "Builtin rule: Excludes this directory from structure validation"
    ]

    # Verify it appears correctly in formatted outputs
    text_output = format_report_text(report)
    assert (
        "Builtin rule: Excludes this directory from structure validation" in text_output
    )

    json_output = format_report_json(report)
    assert (
        "Builtin rule: Excludes this directory from structure validation" in json_output
    )

    markdown_output = format_report_markdown(report)
    assert (
        "Builtin rule: Excludes this directory from structure validation"
        in markdown_output
    )


def test_sorting():
    """Test that reports are sorted correctly."""
    test_yaml = """
structure_rules:
  z_rule:
    - description: 'Z rule'
    - require: 'README\\.md'
  a_rule:
    - description: 'A rule'
    - require: 'LICENSE'

directory_map:
  /z/:
    - description: 'Z directory'
    - use_rule: z_rule
  /a/:
    - description: 'A directory'
    - use_rule: a_rule
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    # Directories should be sorted
    directories = [d.directory for d in report.directory_reports]
    assert directories == ["/a/", "/z/"]

    # Rules should be sorted
    rules = [r.rule_name for r in report.structure_rule_reports]
    assert rules == ["a_rule", "z_rule"]


def test_pattern_formatting():
    """Test that patterns are correctly formatted in structure rule reports."""
    test_yaml = """
structure_rules:
  comprehensive_rule:
    - description: 'Rule with various pattern types'
    - require: 'README\\.md'
    - allow: '.*\\.txt'
    - forbid: 'secret\\.key'
    - allow: 'docs/'
      use_rule: comprehensive_rule

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: comprehensive_rule
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    # Get the structure rule report
    rule_report = report.structure_rule_reports[0]

    assert rule_report.rule_name == "comprehensive_rule"
    assert len(rule_report.patterns) == 4

    # Verify each pattern is formatted correctly
    assert "require: README\\.md" in rule_report.patterns[0]
    assert "allow: .*\\.txt" in rule_report.patterns[1]
    assert "forbid: secret\\.key" in rule_report.patterns[2]
    assert "allow: docs/" in rule_report.patterns[3]
    assert "use_rule: comprehensive_rule" in rule_report.patterns[3]

    # Verify patterns appear in text output
    text_output = format_report_text(report)
    assert "Patterns:" in text_output
    assert "require: README\\.md" in text_output
    assert "allow: .*\\.txt" in text_output
    assert "forbid: secret\\.key" in text_output
    assert "allow: docs/" in text_output
    assert "use_rule: comprehensive_rule" in text_output

    # Verify patterns appear in markdown output
    markdown_output = format_report_markdown(report)
    assert "**Patterns:**" in markdown_output
    assert "require: README\\.md" in markdown_output

    # Verify patterns appear in JSON output
    json_output = format_report_json(report)
    assert "patterns" in json_output
    # Note: JSON escapes backslashes, so \. becomes \\.
    assert "README" in json_output
    assert "patterns" in json_output


def test_get_repository_info_non_git_directory():
    """Test get_repository_info returns None for non-git directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_info = get_repository_info(tmpdir)
        assert repo_info is None


def test_get_repository_info_git_repository():
    """Test get_repository_info returns correct information for git repositories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize a git repository
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmpdir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmpdir,
            check=True,
            capture_output=True,
        )

        # Create an initial commit
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmpdir,
            check=True,
            capture_output=True,
        )

        # Get repository info
        repo_info = get_repository_info(tmpdir)

        # Verify the information
        assert repo_info is not None
        assert repo_info.repository_name == os.path.basename(tmpdir)
        assert repo_info.branch  # Should have a branch (usually main or master)
        assert repo_info.commit_hash  # Should have a commit hash
        assert len(repo_info.commit_hash) == 40  # Git hash is 40 characters
        assert repo_info.commit_date  # Should have a commit date


def test_report_with_repository_info():
    """Test that repository information appears in reports."""
    test_yaml = """
structure_rules:
  basic_rule:
    - description: 'Basic rule for documentation'
    - require: 'README\\.md'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)

    # Generate report with current repository (should be a git repo)
    report = generate_report(config, ".")

    # Check that repository info is present (assuming we're in a git repo)
    if report.repository_info:
        assert report.repository_info.repository_name
        # the branch is empty in CI (detached head check-outs)
        # assert report.repository_info.branch
        assert report.repository_info.commit_hash
        assert report.repository_info.commit_date

        # Verify it appears in text format
        text_output = format_report_text(report)
        assert f"{report.repository_info.repository_name}" in text_output
        assert f"{report.repository_info.branch}" in text_output
        assert f"{report.repository_info.commit_hash}" in text_output
        assert f"{report.repository_info.commit_date}" in text_output

        # Verify it appears in markdown format
        markdown_output = format_report_markdown(report)
        assert "## Repository Information" in markdown_output
        assert f"{report.repository_info.repository_name}" in markdown_output
        assert f"{report.repository_info.branch}" in markdown_output
        assert f"{report.repository_info.commit_hash}`" in markdown_output

        # Verify it appears in JSON format
        json_output = format_report_json(report)
        assert "repository_info" in json_output
        assert report.repository_info.repository_name in json_output
        assert report.repository_info.commit_hash in json_output


def test_report_without_repository_info():
    """Test that reports work correctly when repository info is unavailable."""
    test_yaml = """
structure_rules:
  basic_rule:
    - description: 'Basic rule for documentation'
    - require: 'README\\.md'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: basic_rule
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Generate report in a non-git directory
        report = generate_report(config, tmpdir)

        # Repository info should be None
        assert report.repository_info is None

        # Verify text output doesn't include repository section
        text_output = format_report_text(report)
        assert "Repository Information" not in text_output

        # Verify markdown output doesn't include repository section
        markdown_output = format_report_markdown(report)
        assert "## Repository Information" not in markdown_output

        # Verify JSON output has null repository_info
        json_output = format_report_json(report)
        assert '"repository_info": null' in json_output


def test_companion_requirements_in_report():
    """Test that companion requirements are properly displayed in reports."""
    test_yaml = r"""
structure_rules:
  cpp_with_companions:
    - description: 'C++ files with required header and test companions'
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: '{{base}}.h'
        - require: '{{base}}_test.cpp'
    - allow: '.*\.h'
    - allow: '.*_test\.cpp'

directory_map:
  /:
    - description: 'Root directory'
    - use_rule: cpp_with_companions
"""
    config = Configuration(test_yaml, param1_is_yaml_string=True)
    report = generate_report(config)

    # Get the structure rule report
    rule_report = report.structure_rule_reports[0]

    assert rule_report.rule_name == "cpp_with_companions"
    assert len(rule_report.patterns) == 3

    # Verify companion requirements are in the pattern
    cpp_pattern = rule_report.patterns[0]
    assert "allow: (?P<base>.*)\\.cpp" in cpp_pattern
    assert "requires_companion" in cpp_pattern
    assert "require: {{base}}.h" in cpp_pattern
    assert "require: {{base}}_test.cpp" in cpp_pattern

    # Verify in text output
    text_output = format_report_text(report)
    assert "requires_companion" in text_output
    assert "{{base}}.h" in text_output
    assert "{{base}}_test.cpp" in text_output

    # Verify in markdown output
    markdown_output = format_report_markdown(report)
    assert "requires_companion" in markdown_output
    assert "{{base}}.h" in markdown_output

    # Verify in JSON output
    json_output = format_report_json(report)
    assert "requires_companion" in json_output
