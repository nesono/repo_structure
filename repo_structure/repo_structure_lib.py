"""Common library code for repo_structure."""

import logging
import os
import re
from dataclasses import dataclass, field
from os import DirEntry
from pathlib import Path
from typing import Callable, Final, Literal

IGNORE_RULE: Final = "ignore"
BUILTIN_DIRECTORY_RULES: Final = (IGNORE_RULE,)

_LOGGER = logging.getLogger(__name__)


class ConfigurationParseError(Exception):
    """Raised when the configuration file is invalid."""


class StructureRuleError(Exception):
    """Raised when the structure rules are invalid."""


class TemplateError(Exception):
    """Raised when a template is invalid."""


@dataclass
class RepoEntry:  # pylint: disable=too-many-instance-attributes
    """Wrapper for entries in the directory structure, that store the path
    as a string together with the entry type."""

    path: re.Pattern
    is_dir: bool
    is_required: bool
    is_forbidden: bool
    use_rule: str = ""
    if_exists: list["RepoEntry"] = field(default_factory=list)
    companion: list["RepoEntry"] = field(default_factory=list)
    count: int = 0


@dataclass
class Entry:
    """Internal representation of a directory entry."""

    path: str
    rel_dir: str
    is_dir: bool
    is_symlink: bool


@dataclass
class Flags:
    """Flags for common parsing config settings."""

    follow_symlinks: bool = False
    include_hidden: bool = True
    verbose: bool = False


DirectoryMap = dict[str, list[str]]
StructureRuleList = list[RepoEntry]
StructureRuleMap = dict[str, StructureRuleList]


def normalize_path(path: str) -> str:
    """Normalize path separators for cross-platform compatibility.

    Converts all path separators to forward slashes for consistent
    internal representation across Windows, macOS, and Linux.
    """
    return path.replace(os.sep, "/") if path else path


def join_path_normalized(*parts: str) -> str:
    """Join path parts and normalize separators for cross-platform compatibility.

    Uses pathlib.Path but ensures forward slashes in the result.
    """
    if not parts:
        return ""
    joined = Path(*parts)
    return normalize_path(str(joined))


def rel_dir_to_map_dir(rel_dir: str):
    """Convert a relative directory path to a mapped directory path.

    This function ensures that a given relative directory path conforms to
    a specific format required for mapping. It enforces that the path starts
    and ends with a '/' character.
    """
    if not rel_dir or rel_dir == "/":
        return "/"

    if not rel_dir.startswith("/"):
        rel_dir = "/" + rel_dir
    if not rel_dir.endswith("/"):
        rel_dir = rel_dir + "/"

    return rel_dir


def map_dir_to_rel_dir(map_dir: str) -> str:
    """Convert a mapped directory path to a relative directory path.

    This function takes a mapped directory path and converts it back to
    a relative directory path by removing the leading and trailing '/'
    characters if they exist. If the input is the root directory or empty,
    it returns an empty string.
    """
    if not map_dir or map_dir == "/":
        return ""

    return map_dir[1:-1]


def substitute_pattern_captures(pattern_template: str, captures: dict[str, str]) -> str:
    r"""Substitute captured group values into a pattern template.

    Captured values are passed through ``re.escape`` so any regex
    metacharacters in the captured filename are treated as literals.

    Args:
        pattern_template: Pattern string with {{name}} placeholders
        captures: Dictionary mapping capture group names to their values

    Returns:
        Pattern string with placeholders replaced by escaped captured values

    Example:
        >>> substitute_pattern_captures("{{base}}.h", {"base": "foo"})
        'foo\\.h'
    """
    result = pattern_template
    for name, value in captures.items():
        placeholder = f"{{{{{name}}}}}"
        result = result.replace(placeholder, re.escape(value))
    return result


def extract_pattern_captures(
    pattern: re.Pattern, filename: str
) -> dict[str, str] | None:
    r"""Extract named group captures from a pattern match.

    Args:
        pattern: Compiled regex pattern with named groups
        filename: Filename to match against the pattern

    Returns:
        Dictionary of captured group names to values, or None if no match

    Example:
        >>> pattern = re.compile(r'(?P<base>.*)\.cpp')
        >>> extract_pattern_captures(pattern, 'foo.cpp')
        {'base': 'foo'}
    """
    match = pattern.fullmatch(filename)
    if match:
        return match.groupdict()
    return None


def expand_companion_requirements(
    companion_templates: list["RepoEntry"], captures: dict[str, str]
) -> list["RepoEntry"]:
    """Expand companion requirement templates with captured values.

    Args:
        companion_templates: List of RepoEntry templates with {{name}} placeholders
        captures: Dictionary of captured group values

    Returns:
        List of RepoEntry objects with patterns substituted

    Example:
        If companion has pattern "{{base}}.h" and captures = {"base": "foo"},
        returns RepoEntry with pattern "foo.h"
    """
    expanded = []
    for template in companion_templates:
        # Substitute captures in the pattern (values are re.escaped)
        expanded_pattern = substitute_pattern_captures(template.path.pattern, captures)

        # Compilation failures here indicate a malformed template (not a bad
        # capture value, since those are escaped). Surface them instead of
        # silently dropping required companion checks.
        try:
            compiled_pattern = re.compile(expanded_pattern)
        except re.error as exc:
            raise StructureRuleError(
                f"Companion pattern '{template.path.pattern}' expanded to "
                f"'{expanded_pattern}' which failed to compile: {exc}"
            ) from exc

        expanded_entry = RepoEntry(
            path=compiled_pattern,
            is_dir=template.is_dir,
            is_required=template.is_required,
            is_forbidden=template.is_forbidden,
            use_rule=template.use_rule,
            if_exists=template.if_exists,
            companion=[],
            count=0,
        )
        expanded.append(expanded_entry)

    return expanded


def skip_entry(
    entry: Entry,
    directory_map: DirectoryMap,
    config_file_name: str,
    git_ignore: Callable[[str], bool] | None = None,
    flags: Flags | None = None,
) -> bool:
    """Return True if the entry should be skipped/ignored."""
    if flags is None:
        flags = Flags()
    skip_conditions = [
        (not flags.follow_symlinks and entry.is_symlink),
        (not flags.include_hidden and entry.path.startswith(".")),
        (entry.path == ".gitignore" and not entry.is_dir),
        (entry.path == ".git" and entry.is_dir),
        (git_ignore and git_ignore(entry.path)),
        (
            entry.is_dir
            and rel_dir_to_map_dir(join_path_normalized(entry.rel_dir, entry.path))
            in directory_map
        ),
        (entry.path == config_file_name),
    ]

    for condition in skip_conditions:
        if condition:
            _LOGGER.debug("Skipping %s", entry.path)
            return True

    return False


def to_entry(os_entry: DirEntry[str], rel_dir: str) -> Entry:
    """Convert an os.DirEntry to an internal Entry representation."""
    return Entry(
        path=os_entry.name,
        rel_dir=rel_dir,
        is_dir=os_entry.is_dir(),
        is_symlink=os_entry.is_symlink(),
    )


def expand_use_rule(
    use_rule: str,
    structure_rules: StructureRuleMap,
    flags: Flags,  # pylint: disable=unused-argument
    rel_path: str,
):
    """Expand the use_rule into a list of RepoEntry items."""
    if use_rule:
        _LOGGER.debug("use_rule found for rel path '%s'", rel_path)
        return _build_active_entry_backlog(
            [use_rule],
            structure_rules,
        )
    return None


def expand_if_exists(
    backlog_entry: RepoEntry, flags: Flags
):  # pylint: disable=unused-argument
    """Expand to the entry in `if_exists` or None."""
    if backlog_entry.if_exists:
        _LOGGER.debug("if_exists found for rel path '%s'", backlog_entry.path.pattern)
        return backlog_entry.if_exists
    # the following line can not be reached given a directory entry must be
    # either `use_rule`, or `if_exists`
    return None  # pragma: no cover


def map_dir_to_entry_backlog(
    directory_map: DirectoryMap,
    structure_rules: StructureRuleMap,
    map_dir: str,
) -> StructureRuleList:
    """Get the active entry backlog for a given mapped directory."""

    def _get_use_rules_for_directory(
        directory_map: DirectoryMap, directory: str
    ) -> list[str]:
        d = rel_dir_to_map_dir(directory)
        return directory_map[d]

    use_rules = _get_use_rules_for_directory(directory_map, map_dir)
    return _build_active_entry_backlog(use_rules, structure_rules)


def _has_template_substitution(pattern: str) -> bool:
    """Check if a pattern contains template substitution placeholders like {{name}}."""
    return "{{" in pattern and "}}" in pattern


def _clone_repo_entry(
    entry: RepoEntry, *, is_required: bool | None = None
) -> RepoEntry:
    """Shallow-clone a RepoEntry with count reset to 0.

    Counters live on the per-scan backlog. Cloning prevents scan state from
    leaking back into the shared Configuration.
    """
    return RepoEntry(
        path=entry.path,
        is_dir=entry.is_dir,
        is_required=is_required if is_required is not None else entry.is_required,
        is_forbidden=entry.is_forbidden,
        use_rule=entry.use_rule,
        if_exists=entry.if_exists,
        companion=entry.companion,
        count=0,
    )


def _build_active_entry_backlog(
    active_use_rules: list[str], structure_rules: StructureRuleMap
) -> StructureRuleList:
    result: StructureRuleList = []
    for rule in active_use_rules:
        if rule in BUILTIN_DIRECTORY_RULES:
            continue
        rules = structure_rules[rule]
        # Clone every entry so scan-time mutations (count += 1) do not leak
        # back into Configuration.structure_rules.
        result.extend(_clone_repo_entry(entry) for entry in rules)

        # Add companions without template substitution to initial backlog
        for entry in rules:
            if entry.companion:
                for companion in entry.companion:
                    # Only add if no template substitution needed
                    if not _has_template_substitution(companion.path.pattern):
                        companion_copy = _clone_repo_entry(companion, is_required=False)
                        result.append(companion_copy)
    return result


@dataclass
class ScanIssue:
    """Represents a single finding from a scan.

    severity: "error" or "warning"
    code: short machine-consumable code (e.g., "unused_structure_rule")
    message: human-readable description
    path: optional path context for the issue
    """

    severity: Literal["error", "warning"]
    code: str
    message: str
    path: str | None = None


@dataclass(frozen=True)
class MatchSuccess:
    """Successful match: holds the index of the matched backlog entry."""

    index: int


@dataclass(frozen=True)
class MatchFailure:
    """Failed match: holds the resulting ScanIssue."""

    issue: ScanIssue


MatchResult = MatchSuccess | MatchFailure


def get_matching_item_index(
    backlog: StructureRuleList,
    entry_path: str,
    is_dir: bool,
    verbose: bool = False,  # pylint: disable=unused-argument
) -> MatchResult:
    """Get matching item index without raising exceptions, return result with potential issues."""
    for i, v in enumerate(backlog):
        if v.path.fullmatch(entry_path) and v.is_dir == is_dir:
            if v.is_forbidden:
                return MatchFailure(
                    issue=ScanIssue(
                        severity="error",
                        code="forbidden_entry",
                        message=f"Found forbidden entry: {entry_path}",
                        path=entry_path,
                    )
                )
            _LOGGER.debug("  Found match at index %d: '%s'", i, v.path.pattern)
            return MatchSuccess(index=i)

    display_path = entry_path + "/" if is_dir else entry_path
    return MatchFailure(
        issue=ScanIssue(
            severity="error",
            code="unspecified_entry",
            message=f"Found unspecified entry: '{display_path}'",
            path=entry_path,
        )
    )


def _find_matching_file_in_directory(
    base_dir: str,
    pattern: re.Pattern,
    verbose: bool,  # pylint: disable=unused-argument
) -> bool:
    """Find a file matching the pattern in the directory tree.

    Args:
        base_dir: Base directory to search in
        pattern: Compiled regex pattern to match against
        verbose: Enable verbose output

    Returns:
        True if a matching file is found, False otherwise
    """
    base_path = Path(base_dir)
    if not base_path.is_dir():
        return False

    for root, _dirs, files in os.walk(base_dir):
        for filename in files:
            file_abs = Path(root) / filename
            file_rel = file_abs.relative_to(base_path)
            file_rel_normalized = normalize_path(str(file_rel))

            if pattern.fullmatch(file_rel_normalized):
                _LOGGER.debug("  Found companion: %s", file_rel_normalized)
                return True

    return False


def check_companion_files(
    entry_name: str,
    matched_entry: RepoEntry,
    rel_dir: str,
    verbose: bool = False,
) -> ScanIssue | None:
    """Check if required companion files exist for a matched entry.

    Args:
        entry_name: Name of the file that was matched
        matched_entry: The RepoEntry that was matched
        rel_dir: Relative directory where the file exists
        verbose: Enable verbose output

    Returns:
        ScanIssue if a required companion is missing, None otherwise
    """
    if not matched_entry.companion:
        return None

    # Extract captures from the matched pattern
    captures = extract_pattern_captures(matched_entry.path, entry_name)
    if not captures:
        # Pattern doesn't have named groups, skip companion check
        return None

    # Expand companion requirements with captured values
    expanded_companions = expand_companion_requirements(
        matched_entry.companion, captures
    )

    # Check if required companions exist
    base_dir = rel_dir if rel_dir else "."
    for companion in expanded_companions:
        if not companion.is_required:
            continue

        # Search for file matching the companion pattern
        if not _find_matching_file_in_directory(base_dir, companion.path, verbose):
            _LOGGER.debug(
                "  Missing companion matching pattern: %s", companion.path.pattern
            )
            return ScanIssue(
                severity="error",
                code="missing_companion",
                message=f"Missing required companion file: {companion.path.pattern}",
                path=entry_name,
            )

    return None
