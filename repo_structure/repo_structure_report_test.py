"""Tests for repo_structure report functionality."""

from .repo_structure_config import Configuration
from .repo_structure_report import (
    generate_report,
    format_report_text,
    format_report_json,
    format_report_markdown,
    format_report,
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
    assert "Total Directories: 1" in text_output
    assert "Total Structure Rules: 1" in text_output
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
    assert "**Total Directories:** 1" in markdown_output
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
    assert report.total_structure_rules == 1  # dummy_rule is counted
    assert len(report.directory_reports) == 1
    assert len(report.structure_rule_reports) == 1

    dir_report = report.directory_reports[0]
    assert dir_report.directory == "/"
    assert dir_report.applied_rules == ["ignore"]
    assert dir_report.rule_descriptions == [
        "Builtin rule: Excludes this directory from structure validation"
    ]


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
