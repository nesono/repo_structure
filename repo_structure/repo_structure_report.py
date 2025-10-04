"""Report generation functionality for repo structure configuration."""

import json
import subprocess
import os
from dataclasses import dataclass
from typing import Literal, Any, Optional
from .repo_structure_config import Configuration
from .repo_structure_lib import DirectoryMap, StructureRuleMap


@dataclass
class RepositoryInfo:
    """Repository metadata information."""

    repository_name: Optional[str]
    branch: Optional[str]
    commit_hash: Optional[str]
    commit_date: Optional[str]


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
    patterns: list[str]


@dataclass
class ConfigurationReport:
    """Complete configuration report."""

    directory_reports: list[DirectoryReport]
    structure_rule_reports: list[StructureRuleReport]
    total_directories: int
    total_structure_rules: int
    repository_info: Optional[RepositoryInfo]


def get_repository_info(repo_root: str = ".") -> Optional[RepositoryInfo]:
    """Get repository metadata from git.

    Args:
        repo_root: Root directory of the repository (defaults to current directory)

    Returns:
        RepositoryInfo object with git metadata, or None if not a git repository
    """

    def run_git_command(args: list[str]) -> Optional[str]:
        """Run a git command and return output, or None on failure."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip()
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            return None

    # Check if it's a git repository
    if run_git_command(["rev-parse", "--git-dir"]) is None:
        return None

    # Get repository name from the top-level directory
    repo_path = run_git_command(["rev-parse", "--show-toplevel"])
    repo_name = os.path.basename(repo_path) if repo_path else None

    # Get current branch
    branch = run_git_command(["branch", "--show-current"])

    # Get commit hash
    commit_hash = run_git_command(["rev-parse", "HEAD"])

    # Get commit date
    commit_date = run_git_command(["log", "-1", "--format=%ci", "HEAD"])

    return RepositoryInfo(
        repository_name=repo_name,
        branch=branch,
        commit_hash=commit_hash,
        commit_date=commit_date,
    )


def generate_report(config: Configuration, repo_root: str = ".") -> ConfigurationReport:
    """Generate a comprehensive report of the configuration.

    Args:
        config: The configuration to generate a report for.
        repo_root: Root directory of the repository (defaults to current directory)

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

    repository_info = get_repository_info(repo_root)

    return ConfigurationReport(
        directory_reports=directory_reports,
        structure_rule_reports=structure_rule_reports,
        total_directories=len(directory_reports),
        total_structure_rules=len(structure_rule_reports),
        repository_info=repository_info,
    )


def _generate_directory_reports(
    directory_map: DirectoryMap,
    directory_descriptions: dict[str, str],
    structure_rule_descriptions: dict[str, str],
) -> list[DirectoryReport]:
    """Generate reports for each directory mapping."""
    reports = []

    for directory, rules in directory_map.items():
        rule_descriptions = []
        for rule in rules:
            if rule == "ignore":
                rule_descriptions.append(
                    "Builtin rule: Excludes this directory from structure validation"
                )
            else:
                rule_descriptions.append(
                    structure_rule_descriptions.get(rule, "No description provided")
                )

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

    def _format_pattern(entry) -> str:
        """Format a RepoEntry as a human-readable pattern string."""
        # Determine the pattern type
        if entry.is_forbidden:
            pattern_type = "forbid"
        elif entry.is_required:
            pattern_type = "require"
        else:
            pattern_type = "allow"

        # Get the pattern string
        pattern = entry.path.pattern

        # Add directory indicator if needed
        if entry.is_dir:
            pattern += "/"

        # Build the formatted string
        result = f"{pattern_type}: {pattern}"

        # Add use_rule if present
        if entry.use_rule:
            result += f" (use_rule: {entry.use_rule})"

        # Add requires_companion if present
        if entry.requires_companion:
            companion_patterns = []
            for companion in entry.requires_companion:
                comp_type = "require" if companion.is_required else "allow"
                companion_patterns.append(f"{comp_type}: {companion.path.pattern}")
            result += f" (requires_companion: [{', '.join(companion_patterns)}])"

        return result

    reports = []

    # Check if 'ignore' rule is used anywhere
    ignore_directories = [
        directory for directory, rules in directory_map.items() if "ignore" in rules
    ]

    # Add built-in 'ignore' rule if it's used
    if ignore_directories:
        directory_descs = [
            directory_descriptions.get(directory, "No description provided")
            for directory in ignore_directories
        ]
        reports.append(
            StructureRuleReport(
                rule_name="ignore",
                description="Builtin rule: Excludes this directory from structure validation",
                applied_directories=ignore_directories,
                directory_descriptions=directory_descs,
                rule_count=0,
                patterns=[],
            )
        )

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

        # Format patterns from rule entries
        patterns = [_format_pattern(entry) for entry in rule_entries]

        reports.append(
            StructureRuleReport(
                rule_name=rule_name,
                description=structure_rule_descriptions.get(
                    rule_name, "No description provided"
                ),
                applied_directories=applied_directories,
                directory_descriptions=directory_descs,
                rule_count=len(rule_entries),
                patterns=patterns,
            )
        )

    return sorted(reports, key=lambda x: x.rule_name)


def _normalize_directory_display(directory: str) -> str:
    """Normalize directory path for display with trailing slash.

    Args:
        directory: Directory path to normalize

    Returns:
        Normalized directory path with trailing slash (or '/' for root)
    """
    display_dir = directory.lstrip("/").rstrip("/")
    if not display_dir:
        return "/"
    return display_dir + "/"


def _format_repository_info_text(repo_info: RepositoryInfo) -> list[str]:
    """Format repository information section for text output.

    Args:
        repo_info: Repository information to format

    Returns:
        List of formatted text lines
    """
    lines = []
    lines.append("Repository Information")
    lines.append("-" * 22)
    if repo_info.repository_name:
        lines.append(f"Repository: {repo_info.repository_name}")
    if repo_info.branch:
        lines.append(f"Branch: {repo_info.branch}")
    if repo_info.commit_hash:
        lines.append(f"Commit: {repo_info.commit_hash}")
    if repo_info.commit_date:
        lines.append(f"Date: {repo_info.commit_date}")
    lines.append("")
    return lines


def _format_directory_mappings_text(
    directory_reports: list[DirectoryReport],
) -> list[str]:
    """Format directory mappings section for text output.

    Args:
        directory_reports: List of directory reports to format

    Returns:
        List of formatted text lines
    """
    lines = []
    lines.append("Directory Mappings")
    lines.append("-" * 20)
    for dir_report in directory_reports:
        display_dir = _normalize_directory_display(dir_report.directory)
        lines.append(f"Directory: {display_dir}")
        lines.append(f"  Description: {dir_report.description}")
        lines.append(f"  Applied Rules: {', '.join(dir_report.applied_rules)}")
        for rule, desc in zip(dir_report.applied_rules, dir_report.rule_descriptions):
            lines.append(f"    - {rule}: {desc}")
        lines.append("")
    return lines


def _format_structure_rules_text(
    structure_rule_reports: list[StructureRuleReport],
) -> list[str]:
    """Format structure rules section for text output.

    Args:
        structure_rule_reports: List of structure rule reports to format

    Returns:
        List of formatted text lines
    """
    lines = []
    lines.append("Structure Rules")
    lines.append("-" * 15)
    for rule_report in structure_rule_reports:
        lines.append(f"Rule: {rule_report.rule_name}")
        lines.append(f"  Description: {rule_report.description}")

        # Only show entry count and patterns if there are any
        if rule_report.rule_count > 0:
            lines.append(f"  Entry Count: {rule_report.rule_count}")
            lines.append("  Patterns:")
            for pattern in rule_report.patterns:
                lines.append(f"    - {pattern}")

        display_dirs = [
            _normalize_directory_display(d) for d in rule_report.applied_directories
        ]
        lines.append(f"  Applied to Directories: {', '.join(display_dirs)}")

        for directory, desc in zip(
            rule_report.applied_directories, rule_report.directory_descriptions
        ):
            display_dir = _normalize_directory_display(directory)
            lines.append(f"    - {display_dir}: {desc}")
        lines.append("")
    return lines


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

    if report.repository_info:
        lines.extend(_format_repository_info_text(report.repository_info))

    lines.append("")
    lines.extend(_format_directory_mappings_text(report.directory_reports))
    lines.extend(_format_structure_rules_text(report.structure_rule_reports))

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


def _format_repository_info_markdown(repo_info: RepositoryInfo) -> list[str]:
    """Format repository information as a markdown table.

    Args:
        repo_info: The repository information to format.

    Returns:
        List of formatted lines for the repository info table.
    """
    lines = []
    lines.append("## Repository Information")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("|----------|-------|")
    if repo_info.repository_name:
        lines.append(f"| Repository | {repo_info.repository_name} |")
    if repo_info.branch:
        lines.append(f"| Branch | {repo_info.branch} |")
    if repo_info.commit_hash:
        lines.append(f"| Commit | `{repo_info.commit_hash}` |")
    if repo_info.commit_date:
        lines.append(f"| Date | {repo_info.commit_date} |")
    lines.append("")
    return lines


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

    lines.append("## Introduction")
    lines.append("")
    lines.append(
        "This report provides a comprehensive view of your repository's "
        "structure validation configuration. "
        "It shows how directories are mapped to rules and what those rules enforce."
    )
    lines.append("")
    lines.append(
        "**Directory Maps** define which structure rules apply to specific "
        "directories in your repository. "
        "They map directory paths to the validation rules that govern their contents."
    )
    lines.append("")
    lines.append(
        "**Structure Rules** specify what files and directories are allowed, "
        "required, or forbidden within a directory. "
        "Each rule consists of patterns that match against file paths using "
        "[Python regular expressions]"
        "(https://docs.python.org/3/library/re.html#regular-expression-syntax)."
    )
    lines.append("")

    if report.repository_info:
        lines.extend(_format_repository_info_markdown(report.repository_info))

    # Directory dimension
    lines.append("## Directory Mappings")
    lines.append("")
    for dir_report in report.directory_reports:
        display_dir = _normalize_directory_display(dir_report.directory)
        # Create anchor for this directory
        dir_anchor = dir_report.directory.strip("/").replace("/", "-") or "root"
        lines.append(f"### Directory: `{display_dir}` {{#dir-{dir_anchor}}}")
        lines.append("")
        lines.append(f"**Description:** {dir_report.description}")
        lines.append("")
        lines.append("**Applied Rules:**")
        for rule, desc in zip(dir_report.applied_rules, dir_report.rule_descriptions):
            # Link to the rule section
            lines.append(f"- [`{rule}`](#rule-{rule}): {desc}")
        lines.append("")

    # Structure rule dimension
    lines.append("## Structure Rules")
    lines.append("")
    for rule_report in report.structure_rule_reports:
        # Create anchor for this rule
        lines.append(
            f"### Rule: `{rule_report.rule_name}` {{#rule-{rule_report.rule_name}}}"
        )
        lines.append("")
        lines.append(f"**Description:** {rule_report.description}")

        # Only show entry count and patterns if there are any
        if rule_report.rule_count > 0:
            lines.append(f"**Entry Count:** {rule_report.rule_count}")
            lines.append("")
            lines.append("**Patterns:**")
            for pattern in rule_report.patterns:
                lines.append(f"- `{pattern}`")
            lines.append("")
        else:
            lines.append("")

        lines.append("**Applied to Directories:**")
        for directory, desc in zip(
            rule_report.applied_directories, rule_report.directory_descriptions
        ):
            display_dir = _normalize_directory_display(directory)
            # Link back to the directory section
            dir_anchor = directory.strip("/").replace("/", "-") or "root"
            lines.append(f"- [`{display_dir}`](#dir-{dir_anchor}): {desc}")
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
    if format_type == "markdown":
        return format_report_markdown(report)
    return format_report_text(report)
