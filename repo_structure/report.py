"""Report generation functionality for repo structure configuration."""

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Literal
from .config import Configuration
from .config_merge import unqualify
from .models import (
    BUILTIN_DIRECTORY_RULES,
    IGNORE_RULE,
    RepoEntry,
    StructureRuleList,
)

ReportFormat = Literal["text", "json", "markdown"]
"""Output formats supported by :data:`FORMATTERS`."""


@dataclass
class RepositoryInfo:
    """Repository metadata information."""

    repository_name: str | None
    branch: str | None
    commit_hash: str | None
    commit_date: str | None


@dataclass
class DirectoryReport:
    """Report data for a single directory."""

    directory: str
    description: str
    applied_rules: list[str]
    rule_descriptions: list[str]


@dataclass
class StructureRuleReport:
    """Report data for a single structure rule.

    ``rule_name`` is the name the rule has in the merged configuration, which
    for a rule owned by a mounted configuration is qualified with that
    configuration's path -- ``unqualify`` recovers the name as written in the
    file that defines it. ``source_config`` names that file, and is empty when
    the rule comes from the top-level configuration.
    """

    rule_name: str
    description: str
    applied_directories: list[str]
    directory_descriptions: list[str]
    rule_count: int
    patterns: list[str]
    source_config: str = ""


@dataclass
class ConfigurationReport:
    """Complete configuration report."""

    directory_reports: list[DirectoryReport]
    structure_rule_reports: list[StructureRuleReport]
    total_directories: int
    total_structure_rules: int
    repository_info: RepositoryInfo | None


def get_repository_info(repo_root: str = ".") -> RepositoryInfo | None:
    """Get repository metadata from git.

    Args:
        repo_root: Root directory of the repository (defaults to current directory)

    Returns:
        RepositoryInfo object with git metadata, or None if not a git repository
    """

    def run_git_command(args: list[str]) -> str | None:
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
    repo_name = Path(repo_path).name if repo_path else None

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
    directory_reports = _generate_directory_reports(config)
    structure_rule_reports = _generate_structure_rule_reports(config)

    return ConfigurationReport(
        directory_reports=directory_reports,
        structure_rule_reports=structure_rule_reports,
        total_directories=len(directory_reports),
        total_structure_rules=len(structure_rule_reports),
        repository_info=get_repository_info(repo_root),
    )


def _rule_source(config: Configuration, rule_name: str) -> str:
    """Name the mounted configuration a rule comes from, if it is one.

    Rules of the top-level configuration report an empty source: naming the
    file they came from would be noise in a single-file repository.
    """
    origin = config.rule_origins.get(rule_name, "")
    return "" if origin == config.configuration_file_name else origin


def _rule_anchor(rule_name: str) -> str:
    """Build a markdown anchor id for a rule section.

    Qualified rule names carry a configuration path, so anything that is not
    safe in an anchor collapses to a dash. Plain rule names come through
    unchanged.
    """
    return "rule-" + re.sub(r"[^A-Za-z0-9_-]+", "-", rule_name)


_NO_DESCRIPTION = "No description provided"
_BUILTIN_IGNORE_DESCRIPTION = (
    "Builtin rule: Excludes this directory from structure validation"
)


def _rule_description(config: Configuration, rule_name: str) -> str:
    """Describe a rule, covering the builtin rules the configuration cannot."""
    if rule_name in BUILTIN_DIRECTORY_RULES:
        return _BUILTIN_IGNORE_DESCRIPTION
    return config.structure_rule_descriptions.get(rule_name, _NO_DESCRIPTION)


def _directory_description(config: Configuration, directory: str) -> str:
    """Describe a mapped directory."""
    return config.directory_descriptions.get(directory, _NO_DESCRIPTION)


def _generate_directory_reports(config: Configuration) -> list[DirectoryReport]:
    """Generate reports for each directory mapping."""
    reports = [
        DirectoryReport(
            directory=directory,
            description=_directory_description(config, directory),
            applied_rules=rules,
            rule_descriptions=[_rule_description(config, rule) for rule in rules],
        )
        for directory, rules in config.directory_map.items()
    ]

    return sorted(reports, key=lambda x: x.directory)


def _generate_structure_rule_reports(
    config: Configuration,
) -> list[StructureRuleReport]:
    """Generate reports for each structure rule."""

    def _format_pattern(entry: RepoEntry) -> str:
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

        # Add companion if present
        if entry.companion:
            companion_patterns = []
            for companion in entry.companion:
                comp_type = "require" if companion.is_required else "allow"
                companion_patterns.append(f"{comp_type}: {companion.path.pattern}")
            result += f" (companion: [{', '.join(companion_patterns)}])"

        return result

    def _directories_using(rule_name: str) -> list[str]:
        return [
            directory
            for directory, rules in config.directory_map.items()
            if rule_name in rules
        ]

    def _report_for(rule_name: str, entries: StructureRuleList) -> StructureRuleReport:
        applied_directories = _directories_using(rule_name)
        return StructureRuleReport(
            rule_name=rule_name,
            description=_rule_description(config, rule_name),
            applied_directories=applied_directories,
            directory_descriptions=[
                _directory_description(config, directory)
                for directory in applied_directories
            ],
            rule_count=len(entries),
            patterns=[_format_pattern(entry) for entry in entries],
            source_config=_rule_source(config, rule_name),
        )

    reports = [
        _report_for(rule_name, entries)
        for rule_name, entries in config.structure_rules.items()
    ]

    # The builtin ignore rule has no entry in structure_rules, so it only shows
    # up in the report when some directory actually maps it.
    if _directories_using(IGNORE_RULE):
        reports.append(_report_for(IGNORE_RULE, []))

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
        rule_names = [unqualify(rule) for rule in dir_report.applied_rules]
        lines.append(f"Directory: {display_dir}")
        lines.append(f"  Description: {dir_report.description}")
        lines.append(f"  Applied Rules: {', '.join(rule_names)}")
        for rule, desc in zip(rule_names, dir_report.rule_descriptions):
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
        lines.append(f"Rule: {unqualify(rule_report.rule_name)}")
        if rule_report.source_config:
            lines.append(f"  Defined in: {rule_report.source_config}")
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
    return json.dumps(asdict(report), indent=2)


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


_MARKDOWN_INTRODUCTION = [
    "## Introduction",
    "",
    "This report provides a comprehensive view of your repository's "
    "structure validation configuration. "
    "It shows how directories are mapped to rules and what those rules enforce.",
    "",
    "**Directory Maps** define which structure rules apply to specific "
    "directories in your repository. "
    "They map directory paths to the validation rules that govern their contents.",
    "",
    "**Structure Rules** specify what files and directories are allowed, "
    "required, or forbidden within a directory. "
    "Each rule consists of patterns that match against file paths using "
    "[Python regular expressions]"
    "(https://docs.python.org/3/library/re.html#regular-expression-syntax).",
    "",
]


def _directory_anchor(directory: str) -> str:
    """Build the markdown anchor id of a directory section."""
    return "dir-" + (directory.strip("/").replace("/", "-") or "root")


def _format_directory_mappings_markdown(
    directory_reports: list[DirectoryReport],
) -> list[str]:
    """Format directory mappings section for markdown output.

    Args:
        directory_reports: List of directory reports to format

    Returns:
        List of formatted markdown lines
    """
    lines = ["## Directory Mappings", ""]
    for dir_report in directory_reports:
        display_dir = _normalize_directory_display(dir_report.directory)
        anchor = _directory_anchor(dir_report.directory)
        lines.append(f"### Directory: `{display_dir}` {{#{anchor}}}")
        lines.append("")
        lines.append(f"**Description:** {dir_report.description}")
        lines.append("")
        lines.append("**Applied Rules:**")
        for rule, desc in zip(dir_report.applied_rules, dir_report.rule_descriptions):
            # Link to the rule section
            lines.append(f"- [`{unqualify(rule)}`](#{_rule_anchor(rule)}): {desc}")
        lines.append("")
    return lines


def _format_structure_rules_markdown(
    structure_rule_reports: list[StructureRuleReport],
) -> list[str]:
    """Format structure rules section for markdown output.

    Args:
        structure_rule_reports: List of structure rule reports to format

    Returns:
        List of formatted markdown lines
    """
    lines = ["## Structure Rules", ""]
    for rule_report in structure_rule_reports:
        display_name = unqualify(rule_report.rule_name)
        lines.append(
            f"### Rule: `{display_name}` {{#{_rule_anchor(rule_report.rule_name)}}}"
        )
        lines.append("")
        if rule_report.source_config:
            lines.append(f"**Defined in:** `{rule_report.source_config}`")
            lines.append("")
        lines.append(f"**Description:** {rule_report.description}")

        # Only show entry count and patterns if there are any
        if rule_report.rule_count > 0:
            lines.append(f"**Entry Count:** {rule_report.rule_count}")
            lines.append("")
            lines.append("**Patterns:**")
            lines.extend(f"- `{pattern}`" for pattern in rule_report.patterns)
        lines.append("")

        lines.append("**Applied to Directories:**")
        for directory, desc in zip(
            rule_report.applied_directories, rule_report.directory_descriptions
        ):
            display_dir = _normalize_directory_display(directory)
            # Link back to the directory section
            lines.append(
                f"- [`{display_dir}`](#{_directory_anchor(directory)}): {desc}"
            )
        lines.append("")
    return lines


def format_report_markdown(report: ConfigurationReport) -> str:
    """Format the report as Markdown.

    Args:
        report: The configuration report to format.

    Returns:
        A Markdown representation of the report.
    """
    lines = ["# Repository Structure Configuration Report", ""]
    lines.extend(_MARKDOWN_INTRODUCTION)

    if report.repository_info:
        lines.extend(_format_repository_info_markdown(report.repository_info))

    lines.extend(_format_directory_mappings_markdown(report.directory_reports))
    lines.extend(_format_structure_rules_markdown(report.structure_rule_reports))

    return "\n".join(lines)


FORMATTERS: dict[ReportFormat, Callable[[ConfigurationReport], str]] = {
    "text": format_report_text,
    "json": format_report_json,
    "markdown": format_report_markdown,
}
"""Registry of report formatters, keyed by output format.

Add a new format by registering its formatter here; the CLI derives its
``--output-format`` choices from these keys.
"""


def format_report(
    report: ConfigurationReport,
    format_type: ReportFormat = "text",
) -> str:
    """Format the report in the specified format.

    Args:
        report: The configuration report to format.
        format_type: The desired output format.

    Returns:
        A formatted representation of the report.

    Raises:
        KeyError: If ``format_type`` is not a registered format.
    """
    return FORMATTERS[format_type](report)
