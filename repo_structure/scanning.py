"""Shared scanning helpers: entry skipping, matching and backlog building."""

import logging
import os
import re
from os import DirEntry
from pathlib import Path
from typing import Callable

from .models import (
    BUILTIN_DIRECTORY_RULES,
    DirectoryMap,
    Entry,
    Flags,
    MatchFailure,
    MatchResult,
    MatchSuccess,
    RepoEntry,
    ScanIssue,
    StructureRuleList,
    StructureRuleMap,
)
from .paths import (
    join_path_normalized,
    normalize_path,
    rel_dir_to_map_dir,
)
from .patterns import (
    expand_companion_requirements,
    extract_pattern_captures,
    has_template_substitution,
)

_LOGGER = logging.getLogger(__name__)


def skip_entry(
    entry: Entry,
    directory_map: DirectoryMap,
    config_file_name: str,
    git_ignore: Callable[[str], bool] | None = None,
    flags: Flags | None = None,
) -> bool:
    """Return True if the entry should be skipped/ignored.

    `git_ignore` is called with the entry's path relative to the repository
    root, so it must resolve that against the root rather than the process CWD.
    """
    if flags is None:
        flags = Flags()
    skip_conditions = [
        (not flags.follow_symlinks and entry.is_symlink),
        (not flags.include_hidden and entry.path.startswith(".")),
        (entry.path == ".gitignore" and not entry.is_dir),
        (entry.path == ".git" and entry.is_dir),
        (git_ignore and git_ignore(join_path_normalized(entry.rel_dir, entry.path))),
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
                    if not has_template_substitution(companion.path.pattern):
                        companion_copy = _clone_repo_entry(companion, is_required=False)
                        result.append(companion_copy)
    return result


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
                    code="forbidden_entry", entry_path=entry_path, is_dir=is_dir
                )
            _LOGGER.debug("  Found match at index %d: '%s'", i, v.path.pattern)
            return MatchSuccess(index=i)

    return MatchFailure(code="unspecified_entry", entry_path=entry_path, is_dir=is_dir)


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
    search_dir: str,
    verbose: bool = False,
) -> ScanIssue | None:
    """Check if required companion files exist for a matched entry.

    Args:
        entry_name: Name of the file that was matched
        matched_entry: The RepoEntry that was matched
        search_dir: Directory to search companions in, resolved by the caller
            against the repository root (not the process CWD)
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
    base_dir = search_dir if search_dir else "."
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
