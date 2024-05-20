"""Library functions for repo structure directory verification."""

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from repo_structure_config import Configuration


# Exception for missing mapping
class MissingMappingError(Exception):
    """Exception raised when no directory mapping available for entry."""


class MissingRequiredEntriesError(Exception):
    """Exception raised when required entries are missing."""


class UnspecifiedEntryError(Exception):
    """Exception raised when unspecified entries are found."""


class EntryTypeMismatchError(Exception):
    """Exception raised when unspecified entry type is not matching the found entry."""


class EntryType(Enum):
    """Type of the directory entry, to allow for put all wrappers in a list."""

    FILE = "file"
    DIR = "dir"


class ContentRequirement(Enum):
    """Requirement mode for the directory entry."""

    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass
class BacklogEntryWrapper:
    """Wrapper for entries in the directory structure, that store the path
    as a string together with the entry type."""

    path: re.Pattern
    entry_type: EntryType
    content_requirement: ContentRequirement
    use_rule: str = ""


def _rel_dir_to_map_dir(rel_dir: str):
    return os.path.join("/", rel_dir)


def _get_use_rules_for_directory(config: Configuration, directory: str) -> List[str]:
    d = os.path.join("/", directory)

    if d in config.directory_mappings:
        return config.directory_mappings[d]

    # closest parent directory match
    parent_dir = os.path.dirname(d)
    while parent_dir != "/":
        if parent_dir in config.directory_mappings:
            return config.directory_mappings[parent_dir]
        parent_dir = os.path.dirname(parent_dir)

    if "/" not in config.directory_mappings:
        raise MissingMappingError(f'Directory "{d}" does not have a directory mapping')

    return config.directory_mappings["/"]


def _prepend_map_dir(map_dir: str, entries: List[re.Pattern]) -> List[re.Pattern]:
    return list([re.compile(os.path.join(map_dir, x.pattern)) for x in entries])


def _wrap_entries(
    entry_list: List[re.Pattern],
    map_dir: str,
    entry_type: EntryType,
    content_requirement: ContentRequirement,
) -> List[BacklogEntryWrapper]:
    result: List[BacklogEntryWrapper] = []
    for e in entry_list:
        result.append(
            BacklogEntryWrapper(
                re.compile(
                    os.path.join(map_dir, e.pattern),
                ),
                entry_type,
                content_requirement,
            )
        )
    return result


def _use_rule_to_entries(
    use_rules: Dict[re.Pattern, str],
    map_dir: str,
) -> List[BacklogEntryWrapper]:
    result: List[BacklogEntryWrapper] = []
    for k, v in use_rules.items():
        # TODO: OPTIONAL here is just a guess - we need to store it in the config already
        result.append(
            BacklogEntryWrapper(
                re.compile(os.path.join(map_dir, k.pattern)),
                EntryType.DIR,
                ContentRequirement.OPTIONAL,
                v,
            )
        )
    return result


def _build_active_entry_backlog(
    active_use_rules: List[str], map_dir: str, config: Configuration
) -> List[BacklogEntryWrapper]:
    result: List[BacklogEntryWrapper] = []
    for rule in active_use_rules:
        result.extend(
            _wrap_entries(
                config.structure_rules[rule].required.files,
                map_dir,
                EntryType.FILE,
                ContentRequirement.REQUIRED,
            )
        )
        result.extend(
            _wrap_entries(
                config.structure_rules[rule].optional.files,
                map_dir,
                EntryType.FILE,
                ContentRequirement.OPTIONAL,
            )
        )
        result.extend(
            _wrap_entries(
                config.structure_rules[rule].required.directories,
                map_dir,
                EntryType.DIR,
                ContentRequirement.REQUIRED,
            )
        )
        result.extend(
            _wrap_entries(
                config.structure_rules[rule].optional.directories,
                map_dir,
                EntryType.DIR,
                ContentRequirement.OPTIONAL,
            )
        )
        result.extend(
            _use_rule_to_entries(config.structure_rules[rule].use_rule, map_dir)
        )
    return result


def _map_dir_to_entry_backlog(
    config: Configuration,
    map_dir: str,
) -> List[BacklogEntryWrapper]:
    use_rules = _get_use_rules_for_directory(config, map_dir)
    return _build_active_entry_backlog(use_rules, map_dir, config)


def _get_matching_item_index(
    items: List[BacklogEntryWrapper], needle: str, entry_type: EntryType
) -> int | None:
    for i, v in enumerate(items):
        if re.compile(needle) == v.path and v.entry_type == entry_type:
            return i
        if v.path.match(needle) and v.entry_type == entry_type:
            return i
    return None


def _remove_if_present(
    items: List[BacklogEntryWrapper], needle: str
) -> List[BacklogEntryWrapper]:
    # Not very efficient just yet, but does the job
    result: List[BacklogEntryWrapper] = []
    for item in items:
        if re.compile(needle) == item.path:
            print(f"Full match: {item.path}")
            continue
        if item.path.match(needle):
            print(f"Regex match: {item.path}")
            continue
        result.append(item)

    print(f"Resulting items {result}")
    return result


def _fail_if_required_entries_missing(entry_backlog: List[BacklogEntryWrapper]) -> None:
    missing_required: List[BacklogEntryWrapper] = []
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
    entry_backlog: List[BacklogEntryWrapper],
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

            # Skip other directory mappings
            if _rel_dir_to_map_dir(rel_path) in config.directory_mappings:
                continue

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
        entry_backlog = _map_dir_to_entry_backlog(config, map_dir[1:])

        _fail_if_invalid_repo_structure_recursive(repo_root, "", config, entry_backlog)

        _fail_if_required_entries_missing(entry_backlog)
