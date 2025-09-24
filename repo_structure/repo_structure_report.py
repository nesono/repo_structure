"""Generate human-readable Markdown reports from repository structure configuration."""

from datetime import datetime
from typing import TextIO

from .repo_structure_config import Configuration
from .repo_structure_lib import StructureRuleList


def generate_markdown_report(
    config: Configuration, output_file: str | TextIO | None = None
) -> str:
    """Generate a Markdown report describing the repository structure.

    Args:
        config: Configuration object containing structure rules and directory mappings
        output_file: Optional file path or file object to write the report to

    Returns:
        The generated Markdown report as a string
    """
    report_lines = []

    # Header
    report_lines.extend(
        [
            "# Repository Structure Report",
            "",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "This document describes the enforced repository structure rules and directory mappings.",
            "",
        ]
    )

    # Table of Contents
    report_lines.extend(
        [
            "## Table of Contents",
            "",
            "- [Directory Mappings](#directory-mappings)",
            "- [Structure Rules](#structure-rules)",
            "- [Rule Details](#rule-details)",
            "",
        ]
    )

    # Directory Mappings Overview
    report_lines.extend(
        [
            "## Directory Mappings",
            "",
            "The following directories have structure rules applied:",
            "",
        ]
    )

    # Create directory mappings table
    report_lines.append("| Directory | Applied Rules |")
    report_lines.append("|-----------|---------------|")

    for directory, rules in config.directory_map.items():
        rules_str = ", ".join(f"`{rule}`" for rule in rules)
        report_lines.append(f"| `{directory}` | {rules_str} |")

    report_lines.append("")

    # Structure Rules Overview
    report_lines.extend(
        [
            "## Structure Rules",
            "",
            "The following structure rules are defined:",
            "",
        ]
    )

    for rule_name in config.structure_rules:
        report_lines.append(f"- [`{rule_name}`](#rule-{rule_name.replace('_', '-')})")

    report_lines.append("")

    # Detailed Rule Descriptions
    report_lines.extend(
        [
            "## Rule Details",
            "",
        ]
    )

    for rule_name, rule_entries in config.structure_rules.items():
        report_lines.extend(_generate_rule_section(rule_name, rule_entries))

    # Footer
    report_lines.extend(
        [
            "---",
            "",
            "*This report was automatically generated from the repository structure configuration.*",
            "",
        ]
    )

    markdown_content = "\n".join(report_lines)

    # Write to file if specified
    if output_file:
        if isinstance(output_file, str):
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(markdown_content)
        else:
            output_file.write(markdown_content)

    return markdown_content


def _generate_rule_section(
    rule_name: str, rule_entries: StructureRuleList
) -> list[str]:
    """Generate a section for a specific rule."""
    lines = []

    # Rule header
    lines.extend(
        [
            f"### Rule: `{rule_name}`",
            "",
        ]
    )

    # Count entries by type
    required_files = []
    optional_files = []
    required_dirs = []
    optional_dirs = []
    forbidden_entries = []

    for entry in rule_entries:
        pattern = entry.path.pattern

        if entry.is_forbidden:
            forbidden_entries.append(pattern)
        elif entry.is_dir:
            if entry.is_required:
                required_dirs.append((pattern, entry))
            else:
                optional_dirs.append((pattern, entry))
        else:
            if entry.is_required:
                required_files.append(pattern)
            else:
                optional_files.append(pattern)

    # Required files
    if required_files:
        lines.extend(
            [
                "#### Required Files",
                "",
            ]
        )
        for pattern in required_files:
            lines.append(f"- `{pattern}`")
        lines.append("")

    # Optional files
    if optional_files:
        lines.extend(
            [
                "#### Optional Files",
                "",
            ]
        )
        for pattern in optional_files:
            lines.append(f"- `{pattern}`")
        lines.append("")

    # Required directories
    if required_dirs:
        lines.extend(
            [
                "#### Required Directories",
                "",
            ]
        )
        for pattern, entry in required_dirs:
            lines.append(f"- `{pattern}/`")
            if entry.use_rule:
                lines.append(f"  - *Uses rule: `{entry.use_rule}`*")
            if entry.if_exists:
                lines.append(
                    f"  - *Contains {len(entry.if_exists)} conditional entries*"
                )
        lines.append("")

    # Optional directories
    if optional_dirs:
        lines.extend(
            [
                "#### Optional Directories",
                "",
            ]
        )
        for pattern, entry in optional_dirs:
            lines.append(f"- `{pattern}/`")
            if entry.use_rule:
                lines.append(f"  - *Uses rule: `{entry.use_rule}`*")
            if entry.if_exists:
                lines.append(
                    f"  - *Contains {len(entry.if_exists)} conditional entries*"
                )
        lines.append("")

    # Forbidden entries
    if forbidden_entries:
        lines.extend(
            [
                "#### Forbidden Entries",
                "",
            ]
        )
        for pattern in forbidden_entries:
            lines.append(f"- `{pattern}` ❌")
        lines.append("")

    # Examples section
    examples = _generate_examples(rule_entries)
    if examples:
        lines.extend(
            [
                "#### Examples",
                "",
            ]
        )
        lines.extend(examples)
        lines.append("")

    return lines


def _generate_examples(rule_entries: StructureRuleList) -> list[str]:
    """Generate example file/directory names that would match the patterns."""
    examples = []

    for entry in rule_entries:
        if entry.is_forbidden:
            continue

        pattern = entry.path.pattern

        # Simple pattern matching for common cases
        example_name = _pattern_to_example(pattern)
        if example_name:
            status = "✅ Required" if entry.is_required else "✓ Optional"
            entry_type = "Directory" if entry.is_dir else "File"
            examples.append(f"- `{example_name}` - {entry_type} ({status})")

    return examples


def _pattern_to_example(pattern: str) -> str | None:
    """Convert a regex pattern to a simple example."""
    # Handle common patterns
    if pattern == ".*\\.py":
        return "example.py"
    elif pattern == ".*\\.md":
        return "example.md"
    elif pattern == ".*\\.txt":
        return "example.txt"
    elif pattern == ".*\\.yaml":
        return "example.yaml"
    elif pattern == ".*\\.yml":
        return "example.yml"
    elif pattern == ".*\\.json":
        return "example.json"
    elif pattern == "__init__\\.py":
        return "__init__.py"
    elif pattern == "__main__\\.py":
        return "__main__.py"
    elif pattern == "README\\.md":
        return "README.md"
    elif pattern == "LICENSE":
        return "LICENSE"
    elif pattern.startswith("test_"):
        return pattern.replace("\\", "").replace(".*", "example")
    elif "\\.py" in pattern and "test" in pattern:
        return pattern.replace("\\.", ".").replace(".*", "example")
    elif pattern.count("\\.") == 1 and not pattern.startswith(".*"):
        # Simple literal patterns like "requirements.txt"
        return pattern.replace("\\.", ".")
    elif pattern == ".*":
        return "any-file"

    return None


def generate_directory_tree_report(config: Configuration) -> str:
    """Generate a directory tree visualization of the repository structure."""
    lines = [
        "# Repository Structure Tree",
        "",
        "```",
        "repository/",
    ]

    # Generate tree for each mapped directory
    for directory in sorted(config.directory_map.keys()):
        if directory == "/":
            continue

        # Convert map directory to relative path for display
        display_path = directory.strip("/")
        if display_path:
            lines.append(f"├── {display_path}/")

            # Show rules applied to this directory
            rules = config.directory_map[directory]
            for rule in rules:
                if rule != "ignore":
                    lines.append(f"│   └── [Rule: {rule}]")

    lines.extend(
        [
            "```",
            "",
            "*Tree shows directory structure with applied rules*",
        ]
    )

    return "\n".join(lines)
