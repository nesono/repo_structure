"""Library functions for repo structure directory verification."""

# pylint: disable=import-error, broad-exception-caught

import os

from typing import Callable, Literal
from dataclasses import dataclass
from gitignore_parser import parse_gitignore

from .repo_structure_config import (
    Configuration,
)

from .repo_structure_lib import (
    map_dir_to_rel_dir,
    _skip_entry,
    _to_entry,
    _handle_use_rule,
    _handle_if_exists,
    _map_dir_to_entry_backlog,
    StructureRuleList,
    Flags,
    join_path_normalized,
)


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


@dataclass
class MatchResult:
    """Result of attempting to match an entry against backlog rules."""

    success: bool
    index: int | None = None
    issue: ScanIssue | None = None


def _get_matching_item_index_safe(
    backlog: StructureRuleList,
    entry_path: str,
    is_dir: bool,
    verbose: bool = False,
) -> MatchResult:
    """Get matching item index without raising exceptions, return result with potential issues."""
    for i, v in enumerate(backlog):
        if v.path.fullmatch(entry_path) and v.is_dir == is_dir:
            if v.is_forbidden:
                return MatchResult(
                    success=False,
                    issue=ScanIssue(
                        severity="error",
                        code="forbidden_entry",
                        message=f"Found forbidden entry: {entry_path}",
                        path=entry_path,
                    ),
                )
            if verbose:
                print(f"  Found match at index {i}: '{v.path.pattern}'")
            return MatchResult(success=True, index=i)

    display_path = entry_path + "/" if is_dir else entry_path
    return MatchResult(
        success=False,
        issue=ScanIssue(
            severity="error",
            code="unspecified_entry",
            message=f"Found unspecified entry: '{display_path}'",
            path=entry_path,
        ),
    )


def _check_required_entries_missing(
    rel_dir: str,
    entry_backlog: StructureRuleList,
) -> ScanIssue | None:
    """Check for missing required entries and return a ScanIssue if any are found."""

    def _report_missing_entries(
        missing_files: list[str], missing_dirs: list[str]
    ) -> str:
        result = f"Required patterns missing in  directory '{rel_dir}':\n"
        if missing_files:
            result += "Files:\n"
            result += "".join(f"  - '{file}'\n" for file in missing_files)
        if missing_dirs:
            result += "Directories:\n"
            result += "".join(f"  - '{dir}'\n" for dir in missing_dirs)
        return result

    missing_required: StructureRuleList = []
    for entry in entry_backlog:
        if entry.is_required and entry.count == 0:
            missing_required.append(entry)

    if missing_required:
        missing_required_files = [
            f.path.pattern for f in missing_required if not f.is_dir
        ]
        missing_required_dirs = [d.path.pattern for d in missing_required if d.is_dir]

        return ScanIssue(
            severity="error",
            code="missing_required_entries",
            message=_report_missing_entries(
                missing_required_files, missing_required_dirs
            ),
            path=rel_dir,
        )
    return None


def _check_invalid_repo_structure_recursive(
    repo_root: str,
    rel_dir: str,
    config: Configuration,
    backlog: StructureRuleList,
    flags: Flags,
) -> list[ScanIssue]:
    """Check repository structure recursively and return list of issues."""
    errors: list[ScanIssue] = []

    def _get_git_ignore(rr: str) -> Callable[[str], bool] | None:
        git_ignore_path = os.path.join(rr, ".gitignore")
        if os.path.isfile(git_ignore_path):
            return parse_gitignore(git_ignore_path)
        return None

    git_ignore = _get_git_ignore(repo_root)

    # Sort directory entries for deterministic processing across platforms
    for os_entry in sorted(
        os.scandir(os.path.join(repo_root, rel_dir)), key=lambda e: e.name
    ):
        entry = _to_entry(os_entry, rel_dir)

        if flags.verbose:
            print(f"Checking entry {entry.path}")

        if _skip_entry(
            entry,
            config.directory_map,
            config.configuration_file_name,
            git_ignore,
            flags,
        ):
            continue

        match_result = _get_matching_item_index_safe(
            backlog, entry.path, os_entry.is_dir(), flags.verbose
        )

        if not match_result.success:
            if match_result.issue:
                # Update the path to include the full relative directory context
                match_result.issue.path = join_path_normalized(
                    entry.rel_dir, entry.path
                )
                errors.append(match_result.issue)
            continue

        # At this point we know match_result.index is not None since success is True
        idx = match_result.index
        assert idx is not None  # Type hint for mypy

        backlog[idx].count += 1

        if os_entry.is_dir():
            new_backlog = _handle_use_rule(
                backlog[idx].use_rule,
                config.structure_rules,
                flags,
                entry.path,
            ) or _handle_if_exists(backlog[idx], flags)

            subdirectory_path = join_path_normalized(rel_dir, entry.path)
            errors.extend(
                _check_invalid_repo_structure_recursive(
                    repo_root, subdirectory_path, config, new_backlog, flags
                )
            )

            missing_entry_issue = _check_required_entries_missing(
                subdirectory_path, new_backlog
            )
            if missing_entry_issue:
                errors.append(missing_entry_issue)

    return errors


# pylint: disable=too-many-branches, too-many-nested-blocks


def _process_map_dir_sync(
    map_dir: str, repo_root: str, config: Configuration, flags: Flags = Flags()
) -> list[ScanIssue]:
    """Process a single map directory entry and return issues instead of raising exceptions."""
    errors: list[ScanIssue] = []

    rel_dir = map_dir_to_rel_dir(map_dir)
    backlog = _map_dir_to_entry_backlog(
        config.directory_map, config.structure_rules, rel_dir
    )

    if not backlog:
        if flags.verbose:
            print("backlog empty - returning success")
        return errors

    # Check repository structure using non-throwing functions
    structure_errors = _check_invalid_repo_structure_recursive(
        repo_root,
        rel_dir,
        config,
        backlog,
        flags,
    )
    errors.extend(structure_errors)

    # Check for missing required entries
    missing_entry_issue = _check_required_entries_missing(rel_dir, backlog)
    if missing_entry_issue:
        errors.append(missing_entry_issue)

    return errors


def scan_full_repository(
    repo_root: str,
    config: Configuration,
    flags: Flags = Flags(),
) -> tuple[list[ScanIssue], list[ScanIssue]]:
    """Scan the repository and return a list of issues (errors and warnings).

    This function is a non-throwing variant intended for easier consumption.
    It keeps the old assert_* behavior intact elsewhere.
    """
    assert repo_root is not None
    errors: list[ScanIssue] = []

    # Missing root mapping error
    if "/" not in config.directory_map:
        errors.append(
            ScanIssue(
                severity="error",
                code="missing_root_mapping",
                message="Config does not have a root mapping",
                path="/",
            )
        )
        # Even if root is missing, we can still attempt warnings computation below
        # but there is nothing to process per-map.
    else:
        # Process each mapped directory independently, collecting errors
        for map_dir in config.directory_map:
            map_dir_errors = _process_map_dir_sync(map_dir, repo_root, config, flags)
            errors.extend(map_dir_errors)

    warnings: list[ScanIssue] = []
    # Compute unused rule warnings (do not throw)
    used_rules = set()
    for rules in config.directory_map.values():
        for r in rules:
            if r and r not in ("ignore",):
                used_rules.add(r)
    changed = True
    while changed:
        changed = False
        for rule_name in list(used_rules):
            for entry in config.structure_rules.get(rule_name, []):
                if entry.use_rule and entry.use_rule not in ("ignore",):
                    if entry.use_rule not in used_rules:
                        used_rules.add(entry.use_rule)
                        changed = True
    for rule_name in config.structure_rules.keys():
        if rule_name not in used_rules:
            warnings.append(
                ScanIssue(
                    severity="warning",
                    code="unused_structure_rule",
                    message=f"Unused structure rule '{rule_name}'",
                    path=None,
                )
            )

    # Sort errors and warnings by path for deterministic ordering across platforms
    # None paths go to the end
    errors.sort(key=lambda x: (x.path is None, x.path or "", x.code))
    warnings.sort(key=lambda x: (x.path is None, x.path or "", x.code))

    return errors, warnings
