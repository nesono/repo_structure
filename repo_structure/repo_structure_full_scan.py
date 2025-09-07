"""Library functions for repo structure directory verification."""

# pylint: disable=import-error, broad-exception-caught

import os

from typing import List, Callable, Union, Literal, Optional, Tuple
from dataclasses import dataclass
from gitignore_parser import parse_gitignore

from .repo_structure_config import (
    Configuration,
)

from .repo_structure_lib import (
    map_dir_to_rel_dir,
    _skip_entry,
    _to_entry,
    _get_matching_item_index,
    _handle_use_rule,
    _handle_if_exists,
    _map_dir_to_entry_backlog,
    StructureRuleList,
    Flags,
    UnspecifiedEntryError,
    ForbiddenEntryError,
)


# Exception for missing mapping
class MissingMappingError(Exception):
    """Exception raised when no directory mapping available for entry."""


class MissingRequiredEntriesError(Exception):
    """Exception raised when required entries are missing."""


class EntryTypeMismatchError(Exception):
    """Exception raised when unspecified entry type is not matching the found entry."""


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
    path: Optional[str] = None


def _fail_if_required_entries_missing(
    rel_dir: str,
    entry_backlog: StructureRuleList,
) -> None:

    def _report_missing_entries(
        missing_files: List[str], missing_dirs: List[str]
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

        raise MissingRequiredEntriesError(
            _report_missing_entries(missing_required_files, missing_required_dirs)
        )


def _fail_if_invalid_repo_structure_recursive(
    repo_root: str,
    rel_dir: str,
    config: Configuration,
    backlog: StructureRuleList,
    flags: Flags,
) -> None:

    def _get_git_ignore(rr: str) -> Union[Callable[[str], bool], None]:
        git_ignore_path = os.path.join(rr, ".gitignore")
        if os.path.isfile(git_ignore_path):
            return parse_gitignore(git_ignore_path)
        return None

    git_ignore = _get_git_ignore(repo_root)

    for os_entry in os.scandir(os.path.join(repo_root, rel_dir)):
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

        try:
            idx = _get_matching_item_index(
                backlog,
                entry.path,
                os_entry.is_dir(),
                flags.verbose,
            )
        except UnspecifiedEntryError as err:
            raise UnspecifiedEntryError(
                f"Unspecified entry found: '{entry.rel_dir}/{entry.path}'"
            ) from err
        except ForbiddenEntryError as err:
            raise ForbiddenEntryError(
                f"Forbidden entry found: '{entry.rel_dir}/{entry.path}'"
            ) from err

        backlog_match = backlog[idx]
        backlog_match.count += 1

        if os_entry.is_dir():
            new_backlog = _handle_use_rule(
                backlog_match.use_rule,
                config.structure_rules,
                flags,
                entry.path,
            ) or _handle_if_exists(backlog_match, flags)

            _fail_if_invalid_repo_structure_recursive(
                repo_root,
                os.path.join(rel_dir, entry.path),
                config,
                new_backlog,
                flags,
            )
            _fail_if_required_entries_missing(
                os.path.join(rel_dir, entry.path), new_backlog
            )


def _process_map_dir(
    map_dir: str, repo_root: str, config: Configuration, flags: Flags = Flags()
):
    """Process a single map directory entry."""
    rel_dir = map_dir_to_rel_dir(map_dir)
    backlog = _map_dir_to_entry_backlog(
        config.directory_map, config.structure_rules, rel_dir
    )

    if not backlog:
        if flags.verbose:
            print("backlog empty - returning success")
        return

    _fail_if_invalid_repo_structure_recursive(
        repo_root,
        rel_dir,
        config,
        backlog,
        flags,
    )
    _fail_if_required_entries_missing(rel_dir, backlog)


def assert_full_repository_structure(
    repo_root: str,
    config: Configuration,
    flags: Flags = Flags(),
) -> None:
    """Fail if the repo structure directory is invalid given the configuration."""
    assert repo_root is not None

    if "/" not in config.directory_map:
        raise MissingMappingError("Config does not have a root mapping")

    for map_dir in config.directory_map:
        _process_map_dir(map_dir, repo_root, config, flags)


# pylint: disable=too-many-branches, too-many-nested-blocks


def scan_full_repository(
    repo_root: str,
    config: Configuration,
    flags: Flags = Flags(),
) -> Tuple[List[ScanIssue], List[ScanIssue]]:
    """Scan the repository and return a list of issues (errors and warnings).

    This function is a non-throwing variant intended for easier consumption.
    It keeps the old assert_* behavior intact elsewhere.
    """
    assert repo_root is not None
    errors: List[ScanIssue] = []

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
            try:
                _process_map_dir(map_dir, repo_root, config, flags)
            except MissingRequiredEntriesError as e:
                errors.append(
                    ScanIssue(
                        severity="error",
                        code="missing_required_entries",
                        message=str(e),
                        path=map_dir,
                    )
                )
            except UnspecifiedEntryError as e:
                errors.append(
                    ScanIssue(
                        severity="error",
                        code="unspecified_entry",
                        message=str(e),
                        path=map_dir,
                    )
                )
            except ForbiddenEntryError as e:
                errors.append(
                    ScanIssue(
                        severity="error",
                        code="forbidden_entry",
                        message=str(e),
                        path=map_dir,
                    )
                )
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught,W0718  # pragma: no cover
                # Fallback catch-all to avoid breaking non-throwing contract
                errors.append(
                    ScanIssue(
                        severity="error",
                        code="internal_error",
                        message=str(e),
                        path=map_dir,
                    )
                )

    warnings: List[ScanIssue] = []
    # Compute unused rule warnings (do not throw)
    try:
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
    except Exception:  # pylint: disable=broad-exception-caught  # pragma: no cover
        pass

    return errors, warnings
