"""Report generation functionality for repo structure configuration."""

import json
from dataclasses import dataclass
from typing import Literal, Any
from .repo_structure_config import Configuration
from .repo_structure_lib import DirectoryMap, StructureRuleMap


@dataclass
class DirectoryReport:
    """Report data for a single directory."""

    directory: str
    description: str
    applied_rules: list[str]
    rule_descriptions: list[str]


@dataclass
class StructureRuleReport:
    """Report data for a single structure rule."""

    rule_name: str
    description: str
    applied_directories: list[str]
    directory_descriptions: list[str]
    rule_count: int


@dataclass
class ConfigurationReport:
    """Complete configuration report."""

    directory_reports: list[DirectoryReport]
    structure_rule_reports: list[StructureRuleReport]
    total_directories: int
    total_structure_rules: int


def generate_report(config: Configuration) -> ConfigurationReport:
    """Generate a comprehensive report of the configuration.

    Args:
        config: The configuration to generate a report for.

    Returns:
        A complete configuration report with directory and structure rule information.
    """
    directory_reports = _generate_directory_reports(
        config.directory_map,
        config.directory_descriptions,
        config.structure_rule_descriptions,
    )

    structure_rule_reports = _generate_structure_rule_reports(
        config.structure_rules,
        config.directory_map,
        config.structure_rule_descriptions,
        config.directory_descriptions,
    )

    return ConfigurationReport(
        directory_reports=directory_reports,
        structure_rule_reports=structure_rule_reports,
        total_directories=len(directory_reports),
        total_structure_rules=len(structure_rule_reports),
    )


def _generate_directory_reports(
    directory_map: DirectoryMap,
    directory_descriptions: dict[str, str],
    structure_rule_descriptions: dict[str, str],
) -> list[DirectoryReport]:
    """Generate reports for each directory mapping."""
    reports = []

    for directory, rules in directory_map.items():
        rule_descriptions = [
            structure_rule_descriptions.get(rule, "No description provided")
            for rule in rules
        ]

        reports.append(
            DirectoryReport(
                directory=directory,
                description=directory_descriptions.get(
                    directory, "No description provided"
                ),
                applied_rules=rules,
                rule_descriptions=rule_descriptions,
            )
        )

    return sorted(reports, key=lambda x: x.directory)


def _generate_structure_rule_reports(
    structure_rules: StructureRuleMap,
    directory_map: DirectoryMap,
    structure_rule_descriptions: dict[str, str],
    directory_descriptions: dict[str, str],
) -> list[StructureRuleReport]:
    """Generate reports for each structure rule."""
    reports = []

    for rule_name, rule_entries in structure_rules.items():
        # Find directories that use this rule
        applied_directories = [
            directory
            for directory, rules in directory_map.items()
            if rule_name in rules
        ]

        directory_descs = [
            directory_descriptions.get(directory, "No description provided")
            for directory in applied_directories
        ]

        reports.append(
            StructureRuleReport(
                rule_name=rule_name,
                description=structure_rule_descriptions.get(
                    rule_name, "No description provided"
                ),
                applied_directories=applied_directories,
                directory_descriptions=directory_descs,
                rule_count=len(rule_entries),
            )
        )

    return sorted(reports, key=lambda x: x.rule_name)


def format_report_text(report: ConfigurationReport) -> str:
    """Format the report as plain text.

    Args:
        report: The configuration report to format.

    Returns:
        A formatted text representation of the report.
    """
    lines = []
    lines.append("Repository Structure Configuration Report")
    lines.append("=" * 45)
    lines.append("")
    lines.append(f"Total Directories: {report.total_directories}")
    lines.append(f"Total Structure Rules: {report.total_structure_rules}")
    lines.append("")

    # Directory dimension
    lines.append("Directory Mappings")
    lines.append("-" * 20)
    for dir_report in report.directory_reports:
        lines.append(f"Directory: {dir_report.directory}")
        lines.append(f"  Description: {dir_report.description}")
        lines.append(f"  Applied Rules: {', '.join(dir_report.applied_rules)}")
        for rule, desc in zip(dir_report.applied_rules, dir_report.rule_descriptions):
            lines.append(f"    - {rule}: {desc}")
        lines.append("")

    # Structure rule dimension
    lines.append("Structure Rules")
    lines.append("-" * 15)
    for rule_report in report.structure_rule_reports:
        lines.append(f"Rule: {rule_report.rule_name}")
        lines.append(f"  Description: {rule_report.description}")
        lines.append(f"  Entry Count: {rule_report.rule_count}")
        lines.append(
            f"  Applied to Directories: {', '.join(rule_report.applied_directories)}"
        )
        for directory, desc in zip(
            rule_report.applied_directories, rule_report.directory_descriptions
        ):
            lines.append(f"    - {directory}: {desc}")
        lines.append("")

    return "\n".join(lines)


def format_report_json(report: ConfigurationReport) -> str:
    """Format the report as JSON.

    Args:
        report: The configuration report to format.

    Returns:
        A JSON representation of the report.
    """

    def convert_to_dict(obj: Any) -> Any:
        """Convert dataclass to dictionary for JSON serialization."""
        if hasattr(obj, "__dict__"):
            result = {}
            for key, value in obj.__dict__.items():
                if isinstance(value, list):
                    result[key] = [
                        convert_to_dict(item) if hasattr(item, "__dict__") else item
                        for item in value
                    ]
                else:
                    result[key] = (
                        convert_to_dict(value) if hasattr(value, "__dict__") else value
                    )
            return result
        return obj

    report_dict = convert_to_dict(report)
    return json.dumps(report_dict, indent=2)


def format_report_markdown(report: ConfigurationReport) -> str:
    """Format the report as Markdown.

    Args:
        report: The configuration report to format.

    Returns:
        A Markdown representation of the report.
    """
    lines = []
    lines.append("# Repository Structure Configuration Report")
    lines.append("")
    lines.append(f"**Total Directories:** {report.total_directories}  ")
    lines.append(f"**Total Structure Rules:** {report.total_structure_rules}")
    lines.append("")

    # Directory dimension
    lines.append("## Directory Mappings")
    lines.append("")
    for dir_report in report.directory_reports:
        lines.append(f"### Directory: `{dir_report.directory}`")
        lines.append("")
        lines.append(f"**Description:** {dir_report.description}")
        lines.append("")
        lines.append("**Applied Rules:**")
        for rule, desc in zip(dir_report.applied_rules, dir_report.rule_descriptions):
            lines.append(f"- `{rule}`: {desc}")
        lines.append("")

    # Structure rule dimension
    lines.append("## Structure Rules")
    lines.append("")
    for rule_report in report.structure_rule_reports:
        lines.append(f"### Rule: `{rule_report.rule_name}`")
        lines.append("")
        lines.append(f"**Description:** {rule_report.description}  ")
        lines.append(f"**Entry Count:** {rule_report.rule_count}")
        lines.append("")
        lines.append("**Applied to Directories:**")
        for directory, desc in zip(
            rule_report.applied_directories, rule_report.directory_descriptions
        ):
            lines.append(f"- `{directory}`: {desc}")
        lines.append("")

    return "\n".join(lines)


def format_report(
    report: ConfigurationReport,
    format_type: Literal["text", "json", "markdown"] = "text",
) -> str:
    """Format the report in the specified format.

    Args:
        report: The configuration report to format.
        format_type: The desired output format.

    Returns:
        A formatted representation of the report.
    """
    if format_type == "json":
        return format_report_json(report)
    elif format_type == "markdown":
        return format_report_markdown(report)
    else:
        return format_report_text(report)
