"""Shared scanning helpers: entry skipping, matching and backlog building."""

import logging
import os
import re
from os import DirEntry
from pathlib import Path
from typing import Callable

from .models import (
    BUILTIN_DIRECTORY_RULES,
    Backlog,
    BacklogEntry,
    DirectoryMap,
    Entry,
    Flags,
    MatchFailure,
    MatchResult,
    MatchSuccess,
    RepoEntry,
    ScanIssue,
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
    config_file_names: set[str],
    git_ignore: Callable[[str], bool] | None = None,
    flags: Flags | None = None,
) -> bool:
    """Return True if the entry should be skipped/ignored.

    `git_ignore` is called with the entry's path relative to the repository
    root, so it must resolve that against the root rather than the process CWD.

    `config_file_names` holds every configuration file taking part in the scan.
    A configuration mounted through `use_config` lives in the subdirectory it
    governs, so entries are matched on their repository-root relative path as
    well as on their bare name.
    """
    if flags is None:
        flags = Flags()
    rel_path = join_path_normalized(entry.rel_dir, entry.path)
    # Ordered cheapest first and chained with `or`, so gitignore matching --
    # by far the most expensive check -- only runs when nothing else decided.
    skip = (
        (not flags.follow_symlinks and entry.is_symlink)
        or (not flags.include_hidden and entry.path.startswith("."))
        or (entry.path == ".gitignore" and not entry.is_dir)
        or (entry.path == ".git" and entry.is_dir)
        or entry.path in config_file_names
        or rel_path in config_file_names
        or (entry.is_dir and rel_dir_to_map_dir(rel_path) in directory_map)
        or (git_ignore is not None and git_ignore(rel_path))
    )

    if skip:
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


def child_backlog(
    matched: BacklogEntry, structure_rules: StructureRuleMap
) -> Backlog | None:
    """Build the backlog that applies inside a matched directory entry.

    A directory entry either recurses into a structure rule via ``use_rule`` or
    carries its contents inline via ``if_exists``, so exactly one of the two
    decides what is allowed below it. Returns None when neither does, meaning
    the directory's contents are not described at all.
    """
    entry = matched.entry
    if entry.use_rule:
        _LOGGER.debug("use_rule found for '%s'", entry.path.pattern)
        return _build_active_entry_backlog(
            [entry.use_rule],
            structure_rules,
        )
    if entry.if_exists:
        _LOGGER.debug("if_exists found for '%s'", entry.path.pattern)
        # A fresh backlog per matched directory: sibling directories governed
        # by the same `if_exists` must not share match counts.
        return [_to_backlog_entry(child) for child in entry.if_exists]
    return None


def map_dir_to_entry_backlog(
    directory_map: DirectoryMap,
    structure_rules: StructureRuleMap,
    map_dir: str,
) -> Backlog:
    """Get the active entry backlog for a given mapped directory."""
    use_rules = directory_map[rel_dir_to_map_dir(map_dir)]
    return _build_active_entry_backlog(use_rules, structure_rules)


def _to_backlog_entry(
    entry: RepoEntry, *, is_required: bool | None = None
) -> BacklogEntry:
    """Put a configured entry on a backlog, with a match counter of its own."""
    return BacklogEntry(
        entry=entry,
        is_required=entry.is_required if is_required is None else is_required,
    )


def _build_active_entry_backlog(
    active_use_rules: list[str], structure_rules: StructureRuleMap
) -> Backlog:
    result: Backlog = []
    for rule in active_use_rules:
        if rule in BUILTIN_DIRECTORY_RULES:
            continue
        for entry in structure_rules[rule]:
            result.append(_to_backlog_entry(entry))
            # Companions that need no template substitution are allowed
            # outright; the ones that do are checked against the file whose
            # captures expand them, so they never join the backlog.
            result.extend(
                _to_backlog_entry(companion, is_required=False)
                for companion in entry.companion
                if not has_template_substitution(companion.path.pattern)
            )
    return result


def get_matching_item_index(
    backlog: Backlog,
    entry_path: str,
    is_dir: bool,
) -> MatchResult:
    """Get matching item index without raising exceptions, return result with potential issues."""
    for i, candidate in enumerate(backlog):
        entry = candidate.entry
        if entry.path.fullmatch(entry_path) and entry.is_dir == is_dir:
            if entry.is_forbidden:
                return MatchFailure(
                    code="forbidden_entry", entry_path=entry_path, is_dir=is_dir
                )
            _LOGGER.debug("  Found match at index %d: '%s'", i, entry.path.pattern)
            return MatchSuccess(index=i)

    return MatchFailure(code="unspecified_entry", entry_path=entry_path, is_dir=is_dir)


def _list_files_below(base_dir: str) -> list[str]:
    """List every file below ``base_dir``, as normalized relative paths."""
    base_path = Path(base_dir)
    if not base_path.is_dir():
        return []

    return [
        normalize_path(str((Path(root) / filename).relative_to(base_path)))
        for root, _dirs, files in os.walk(base_dir)
        for filename in files
    ]


class CompanionIndex:  # pylint: disable=too-few-public-methods
    """Directory listings shared by the companion checks of one scan.

    A companion is searched for anywhere below the directory of the file that
    names it, so every check walks a whole subtree. Since a directory of N
    modules each requiring a companion asks about the same subtree N times,
    the listing is walked once and answered from memory afterwards.

    Deliberately scoped to a single scan: a longer-lived index would answer
    from a listing the filesystem has since moved on from.
    """

    def __init__(self) -> None:
        self._listings: dict[str, list[str]] = {}

    def contains_match(self, base_dir: str, pattern: re.Pattern) -> bool:
        """Return True if any file below ``base_dir`` fully matches ``pattern``."""
        listing = self._listings.get(base_dir)
        if listing is None:
            listing = _list_files_below(base_dir)
            self._listings[base_dir] = listing

        for rel_path in listing:
            if pattern.fullmatch(rel_path):
                _LOGGER.debug("  Found companion: %s", rel_path)
                return True
        return False


def check_companion_files(
    entry_name: str,
    matched_entry: RepoEntry,
    search_dir: str,
    companions: CompanionIndex,
) -> ScanIssue | None:
    """Check if required companion files exist for a matched entry.

    Args:
        entry_name: Name of the file that was matched
        matched_entry: The RepoEntry that was matched
        search_dir: Directory to search companions in, resolved by the caller
            against the repository root (not the process CWD)
        companions: Directory listings for the scan in progress

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
        if not companions.contains_match(base_dir, companion.path):
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
