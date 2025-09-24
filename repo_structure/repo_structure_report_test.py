#!/usr/bin/env python3
"""Test cases for the markdown report generation functionality."""

import tempfile
from io import StringIO

from .repo_structure_config import Configuration
from .repo_structure_report import generate_markdown_report


class TestGenerateMarkdownReport:
    """Test cases for generate_markdown_report function."""

    def test_empty_config(self) -> None:
        """Test report generation with minimal empty config."""
        # Create a configuration with minimal valid YAML content
        yaml_content = """
directory_map: {}
structure_rules: {}
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        assert "# Repository Structure Report" in report
        assert "## Directory Mappings" in report
        assert "## Structure Rules" in report

    def test_simple_directory_mapping(self) -> None:
        """Test report with a simple directory mapping."""
        yaml_content = """
directory_map:
  /src/:
    - use_rule: "python_files"

structure_rules:
  python_files:
    - require: '.*\.py'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        assert "# Repository Structure Report" in report
        assert "src" in report
        assert "python_files" in report

    def test_multiple_directory_mappings(self) -> None:
        """Test report with multiple directory mappings."""
        yaml_content = """
directory_map:
  /src/:
    - use_rule: "python_files"
  /tests/:
    - use_rule: "test_files"
  /docs/:
    - use_rule: "documentation"

structure_rules:
  python_files:
    - require: '.*\.py'
  test_files:
    - require: '.*/test_.*\.py'
    - require: '.*_test\.py'
  documentation:
    - require: '.*\.md'
    - require: '.*\.rst'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        assert "# Repository Structure Report" in report
        assert "src" in report
        assert "tests" in report
        assert "docs" in report
        assert "python_files" in report
        assert "test_files" in report
        assert "documentation" in report

    def test_complex_structure_rules(self) -> None:
        """Test report with complex structure rules."""
        yaml_content = """
directory_map:
  /src/app/:
    - use_rule: "application_code"
  /src/lib/:
    - use_rule: "library_code"

structure_rules:
  application_code:
    - require: '.*\.py'
    - forbid: '.*/__pycache__/.*'
    - forbid: '.*\.pyc'
  library_code:
    - require: '.*\.py'
    - require: '.*/__init__\.py'
    - forbid: '.*/test_.*'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        assert "# Repository Structure Report" in report
        assert "src/app" in report
        assert "src/lib" in report
        assert "application_code" in report
        assert "library_code" in report
        assert ".*\.py" in report
        assert ".*/__init__\.py" in report

    def test_output_to_string_io(self) -> None:
        """Test writing report to StringIO."""
        yaml_content = """
directory_map:
  /src/:
    - use_rule: "source_files"

structure_rules:
  source_files:
    - require: '.*\.py'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        output = StringIO()
        result = generate_markdown_report(config, output)

        output_content = output.getvalue()

        # Should return the same content that was written
        assert result == output_content
        assert "# Repository Structure Report" in output_content
        assert "src" in output_content

    def test_output_to_file(self) -> None:
        """Test writing report to file."""
        yaml_content = """
directory_map:
  /lib/:
    - use_rule: "library_files"

structure_rules:
  library_files:
    - require: '.*\.py'
    - require: '.*\.pyi'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        with tempfile.NamedTemporaryFile(mode="w+", suffix=".md", delete=False) as f:
            result = generate_markdown_report(config, f.name)

            # Read the file content
            with open(f.name, "r", encoding="utf-8") as read_f:
                file_content = read_f.read()

            # Should return the same content that was written
            assert result == file_content
            assert "# Repository Structure Report" in file_content
            assert "lib" in file_content

    def test_report_structure_order(self) -> None:
        """Test that report sections appear in the correct order."""
        yaml_content = """
directory_map:
  /src/:
    - use_rule: "source_code"

structure_rules:
  source_code:
    - require: '.*\.py'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        # Find positions of key sections
        title_pos = report.find("# Repository Structure Report")
        mappings_pos = report.find("## Directory Mappings")
        rules_pos = report.find("## Structure Rules")

        # Verify order
        assert title_pos < mappings_pos < rules_pos
        assert title_pos != -1
        assert mappings_pos != -1
        assert rules_pos != -1

    def test_timestamp_inclusion(self) -> None:
        """Test that report includes generation timestamp."""
        yaml_content = """
directory_map: {}
structure_rules: {}
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        assert "Generated on:" in report
        # Should include current date (at least year)
        assert "2025" in report

    def test_builtin_rules(self) -> None:
        """Test report with built-in directory rules."""
        yaml_content = """
directory_map:
  /src/:
    - use_rule: "python_files"
  /tests/:
    - use_rule: "python_files"

structure_rules:
  python_files:
    - require: '.*\.py'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        assert "# Repository Structure Report" in report
        assert "src" in report
        assert "tests" in report
        assert "python_files" in report
        assert "python_files" in report

    def test_markdown_escaping(self) -> None:
        """Test proper Markdown formatting and escaping."""
        yaml_content = """
directory_map:
  "/path with spaces/":
    - use_rule: "special_rule"
  "/path/with/slashes/":
    - use_rule: "another_rule"

structure_rules:
  special_rule:
    - require: '.*\.py'
  another_rule:
    - require: '.*\.md'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        # Check that paths are properly formatted
        assert "path with spaces" in report
        assert "path/with/slashes" in report
        assert "special_rule" in report
        assert "another_rule" in report

    def test_complex_patterns(self) -> None:
        """Test report with complex file patterns."""
        yaml_content = """
directory_map:
  /src/:
    - use_rule: "complex_patterns"

structure_rules:
  complex_patterns:
    - allow: '.*\.(py|pyi)'
    - forbid: '.*/__pycache__/.*'
    - forbid: '.*\.pyc'
    - forbid: '.*\.pyo'
    - allow: '.*/test_.*\.py'
    - allow: '.*_test\.py'
"""
        config = Configuration(yaml_content, param1_is_yaml_string=True)

        report = generate_markdown_report(config)

        assert "# Repository Structure Report" in report
        assert ".*\.(py|pyi)" in report
        assert ".*/__pycache__/.*" in report
        assert ".*/test_.*\.py" in report
