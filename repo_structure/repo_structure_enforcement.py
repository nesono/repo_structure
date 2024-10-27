"""Library functions for repo structure directory verification."""

# pylint: disable=import-error

import os
import re
from os import DirEntry
from dataclasses import dataclass, replace

from typing import List, Callable, Optional, Union
from gitignore_parser import parse_gitignore

from .repo_structure_config import (
    Configuration,
    RepoEntry,
    StructureRuleList,
)

from .repo_structure_lib import rel_dir_to_map_dir, map_dir_to_rel_dir


@dataclass
class Flags:
    """Flags for common parsing config settings."""

    follow_symlinks: bool = False
    include_hidden: bool = True
    verbose: bool = False


# Exception for missing mapping
class MissingMappingError(Exception):
    """Exception raised when no directory mapping available for entry."""


class MissingRequiredEntriesError(Exception):
    """Exception raised when required entries are missing."""


class UnspecifiedEntryError(Exception):
    """Exception raised when unspecified entries are found."""


class EntryTypeMismatchError(Exception):
    """Exception raised when unspecified entry type is not matching the found entry."""


def _build_active_entry_backlog(
    active_use_rules: List[str], rel_dir: str, config: Configuration
) -> StructureRuleList:
    result: StructureRuleList = []
    for rule in active_use_rules:
        for e in config.structure_rules[rule]:
            result.append(
                replace(e, path=re.compile(os.path.join(rel_dir, e.path.pattern)))
            )
    return result


def _get_matching_item_index(
    backlog: StructureRuleList,
    entry_path: str,
    is_dir: bool,
    verbose: bool = False,
) -> List[int]:
    result: List[int] = []
    for i, v in enumerate(backlog):
        if verbose:
            print(f"  Matching against {v.path}")
        if v.path.fullmatch(entry_path) and v.is_dir == is_dir:
            if verbose:
                print(f"  Found match at index {i}")
            result.append(i)
    if len(result) != 0:
        return result

    if is_dir:
        entry_path += "/"
    raise UnspecifiedEntryError(f"Found unspecified entry: {entry_path}")


def _fail_if_required_entries_missing(
    entry_backlog: StructureRuleList,
) -> None:
    missing_required: StructureRuleList = []
    for entry in entry_backlog:
        if entry.is_required and entry.count == 0:
            missing_required.append(entry)

    if missing_required:
        missing_required_files = [f.path for f in missing_required if not f.is_dir]
        missing_required_dirs = [d.path for d in missing_required if d.is_dir]
        raise MissingRequiredEntriesError(
            f"Required entries missing:\nFiles: "
            f"{missing_required_files}\nDirs: {missing_required_dirs}"
        )


def _fail_if_invalid_repo_structure_recursive(
    repo_root: str,
    rel_dir: str,
    config: Configuration,
    backlog: StructureRuleList,
    flags: Flags,
) -> None:
    git_ignore = _get_git_ignore(repo_root)

    # go through all the files in the repository
    for entry in os.scandir(os.path.join(repo_root, rel_dir)):
        rel_path = os.path.join(rel_dir, entry.name)
        if flags.verbose:
            print(f"Checking entry {rel_path}")

        if _skip_entry(entry, rel_path, config, git_ignore, flags):
            continue

        # go through all found matches in the entry_backlog
        for idx in _get_matching_item_index(
            backlog,
            rel_path,
            entry.is_dir(),
            flags.verbose,
        ):
            backlog_entry = backlog[idx]
            backlog_entry.count += 1
            if flags.verbose:
                print(f"  Registered usage for path {rel_path}")

            if entry.is_dir():
                _handle_use_rule(
                    backlog, backlog_entry.use_rule, config, flags, rel_path
                )
                _handle_if_exists(backlog, backlog_entry, rel_path, flags)

                # enter the subdirectory recursively
                _fail_if_invalid_repo_structure_recursive(
                    repo_root, rel_path, config, backlog, flags
                )


def _handle_use_rule(
    backlog: StructureRuleList,
    use_rule: str,
    config: Configuration,
    flags: Flags,
    rel_path: str,
):
    if use_rule:
        if flags.verbose:
            print(f"use_rule found for rel path {rel_path}")
        backlog.extend(
            _build_active_entry_backlog(
                [use_rule],
                rel_path,
                config,
            )
        )


def _handle_if_exists(
    backlog: StructureRuleList, backlog_entry: RepoEntry, rel_path: str, flags: Flags
):
    if backlog_entry.if_exists:
        if flags.verbose:
            print(f"if_exists found for rel path {backlog_entry.path.pattern}")
        for e in backlog_entry.if_exists:
            backlog.append(
                replace(e, path=re.compile(os.path.join(rel_path, e.path.pattern)))
            )


def _get_git_ignore(repo_root: str) -> Union[Callable[[str], bool], None]:
    git_ignore_path = os.path.join(repo_root, ".gitignore")
    if os.path.isfile(git_ignore_path):
        return parse_gitignore(git_ignore_path)
    return None


def _skip_entry(
    entry: DirEntry[str],
    rel_path: str,
    config: Configuration,
    git_ignore: Union[Callable[[str], bool], None] = None,
    flags: Flags = Flags(),
) -> bool:
    skip_conditions = [
        (not flags.follow_symlinks and entry.is_symlink()),
        (not flags.include_hidden and entry.name.startswith(".")),
        (rel_path == ".gitignore" and entry.is_file()),
        (rel_path == ".git" and entry.is_dir()),
        (git_ignore and git_ignore(entry.path)),
        (entry.is_dir() and rel_dir_to_map_dir(rel_path) in config.directory_map),
    ]

    for condition in skip_conditions:
        if condition:
            if flags.verbose:
                print(f"Skipping {rel_path}")
            return True

    return False


def _map_dir_to_entry_backlog(
    config: Configuration,
    map_dir: str,
) -> StructureRuleList:

    def _get_use_rules_for_directory(
        config: Configuration, directory: str
    ) -> List[str]:
        d = rel_dir_to_map_dir(directory)
        return config.directory_map[d]

    use_rules = _get_use_rules_for_directory(config, map_dir)
    return _build_active_entry_backlog(use_rules, map_dir, config)


def assert_full_repository_structure(
    repo_root: str,
    config: Configuration,
    flags: Optional[Flags] = Flags(),
) -> None:
    """Fail if the repo structure directory is invalid given the configuration."""
    assert repo_root is not None

    # ensure root mapping is there
    if "/" not in config.directory_map:
        raise MissingMappingError("Config does not have a root mapping")

    for map_dir in config.directory_map:
        rel_dir = map_dir_to_rel_dir(map_dir)
        backlog = _map_dir_to_entry_backlog(config, rel_dir)

        # parse directory and burn down backlog
        _fail_if_invalid_repo_structure_recursive(
            repo_root,
            rel_dir,
            config,
            backlog,
            flags or Flags(),
        )
        # report non-empty backlog
        _fail_if_required_entries_missing(backlog)


def assert_path(
    repo_root: str,
    config: Configuration,
    path: str,
    flags: Flags,
) -> None:
    """Fail if the given path is invalid according to the configuration.

    Note that this function will not be able to ensure if all required
    entries are present."""

    def count_common_prefix_characters(str1: str, str2: str) -> int:
        min_length = min(len(str1), len(str2))
        common_char_count = 0

        for i in range(min_length):
            if str1[i] == str2[i]:
                common_char_count += 1
            else:
                break
        return common_char_count

    overlap_max = -1
    max_map_dir = None
    for map_dir in config.directory_map:
        overlap = count_common_prefix_characters(map_dir_to_rel_dir(map_dir), path)
        if overlap > overlap_max:
            overlap_max = overlap
            max_map_dir = map_dir

    if max_map_dir is None:
        raise MissingMappingError(f"No mapping found for path {path}")

    if flags.verbose:
        print(f"Found max overlap between {path} and {max_map_dir}: {overlap_max}")

    rel_dir = map_dir_to_rel_dir(max_map_dir)
    backlog = _map_dir_to_entry_backlog(config, rel_dir)
    path_is_dir = os.path.isdir(os.path.join(repo_root, path))

    # find path in backlog
    index = _get_matching_item_index(
        backlog,
        path,
        path_is_dir,
        flags.verbose,
    )

    if flags.verbose:
        print(f"Found entry in backlog with index {index}")
