"""Library functions for repo structure directory verification."""

import os
import re
from typing import List

from repo_structure_config import (
    Configuration,
    ContentRequirement,
    DirectoryEntryWrapper,
    EntryType,
)


# Exception for missing mapping
class MissingMappingError(Exception):
    """Exception raised when no directory mapping available for entry."""


class MissingRequiredEntriesError(Exception):
    """Exception raised when required entries are missing."""


class UnspecifiedEntryError(Exception):
    """Exception raised when unspecified entries are found."""


class EntryTypeMismatchError(Exception):
    """Exception raised when unspecified entry type is not matching the found entry."""


def _rel_dir_to_map_dir(rel_dir: str):
    if not rel_dir or rel_dir == "/":
        return "/"

    if not rel_dir.startswith("/"):
        rel_dir = "/" + rel_dir
    if not rel_dir.endswith("/"):
        rel_dir = rel_dir + "/"

    return rel_dir


def _map_dir_to_rel_dir(map_dir: str):
    if not map_dir or map_dir == "/":
        return ""

    return map_dir[1:-1]


def _get_use_rules_for_directory(config: Configuration, directory: str) -> List[str]:
    d = _rel_dir_to_map_dir(directory)

    if d in config.directory_mappings:
        return config.directory_mappings[d]

    raise MissingMappingError(f'Directory "{d}" does not have a directory mapping')


def _build_active_entry_backlog(
    active_use_rules: List[str], map_dir: str, config: Configuration
) -> List[DirectoryEntryWrapper]:
    result: List[DirectoryEntryWrapper] = []
    for rule in active_use_rules:
        for e in config.structure_rules[rule].entries:
            result.append(
                DirectoryEntryWrapper(
                    re.compile(os.path.join(map_dir, e.path.pattern)),
                    e.entry_type,
                    e.content_requirement,
                    e.use_rule,
                )
            )
    return result


def _map_dir_to_entry_backlog(
    config: Configuration,
    map_dir: str,
) -> List[DirectoryEntryWrapper]:
    use_rules = _get_use_rules_for_directory(config, map_dir)
    return _build_active_entry_backlog(use_rules, map_dir, config)


def _get_matching_item_index(
    items: List[DirectoryEntryWrapper], needle: str, entry_type: EntryType
) -> int | None:
    for i, v in enumerate(items):
        if re.compile(needle) == v.path and v.entry_type == entry_type:
            return i
        if v.path.fullmatch(needle) and v.entry_type == entry_type:
            return i
    return None


def _fail_if_required_entries_missing(
    entry_backlog: List[DirectoryEntryWrapper],
) -> None:
    missing_required: List[DirectoryEntryWrapper] = []
    for entry in entry_backlog:
        if entry.content_requirement == ContentRequirement.REQUIRED:
            missing_required.append(entry)

    if missing_required:
        missing_required_files = [
            f.path for f in missing_required if f.entry_type == EntryType.FILE
        ]
        missing_required_dirs = [
            d.path for d in missing_required if d.entry_type == EntryType.DIR
        ]
        raise MissingRequiredEntriesError(
            f"Required entries missing:\nFiles: "
            f"{missing_required_files}\nDirs: {missing_required_dirs}"
        )


def _fail_if_invalid_repo_structure_recursive(
    repo_root: str,
    rel_dir: str,
    config: Configuration,
    entry_backlog: List[DirectoryEntryWrapper],
) -> None:
    for entry in os.scandir(os.path.join(repo_root, rel_dir)):
        rel_path = os.path.join(rel_dir, entry.name)
        entry_type = EntryType.DIR if entry.is_dir() else EntryType.FILE
        print(f"rel path: {rel_path}")
        print(f"  before - entry backlog: {entry_backlog}")
        idx = _get_matching_item_index(entry_backlog, rel_path, entry_type)
        print(f"  idx: {idx}")
        if idx is None:
            raise UnspecifiedEntryError(f"Found unspecified entry: {rel_path}")

        # FILE CASE
        if entry.is_file():
            if entry_backlog[idx].entry_type != EntryType.FILE:
                raise EntryTypeMismatchError(f"File {rel_path} matches directory")
            del entry_backlog[idx]

        # DIRECTORY CASE
        elif entry.is_dir():
            if entry_backlog[idx].entry_type != EntryType.DIR:
                raise EntryTypeMismatchError(f"Directory {rel_path} matches file")

            # Skip other directory mappings
            if _rel_dir_to_map_dir(rel_path) in config.directory_mappings:
                print(f"  skipping {rel_path}")
                print(" ", config.directory_mappings.keys())
                del entry_backlog[idx]
                continue

            new_rules = []
            # Recursive use_rule handling (single use_rule supported only)
            if entry_backlog[idx].use_rule:
                new_rules.extend(
                    _build_active_entry_backlog(
                        [entry_backlog[idx].use_rule],
                        rel_path,
                        config,
                    )
                )

            del entry_backlog[idx]
            print(f"  after delete - entry backlog: {entry_backlog}")
            entry_backlog.extend(new_rules)

            # enter the subdirectory
            _fail_if_invalid_repo_structure_recursive(
                repo_root, rel_path, config, entry_backlog
            )
        print(f"  after - entry backlog: {entry_backlog}")


def fail_if_invalid_repo_structure(
    repo_root: "str | None", config: Configuration
) -> None:
    """Fail if the repo structure directory is invalid given the configuration."""
    if repo_root is None:
        return

    # ensure root mapping is there
    if "/" not in config.directory_mappings:
        raise MissingMappingError("Config does not have a root mapping")

    for map_dir in config.directory_mappings:
        rel_dir = _map_dir_to_rel_dir(map_dir)
        entry_backlog = _map_dir_to_entry_backlog(config, rel_dir)
        _fail_if_invalid_repo_structure_recursive(
            repo_root, rel_dir, config, entry_backlog
        )
        _fail_if_required_entries_missing(entry_backlog)
