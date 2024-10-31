"""Library functions for repo structure directory verification."""

# pylint: disable=import-error

import os
import re
from os import DirEntry
from dataclasses import dataclass, replace

from typing import List, Callable, Optional, Union, Iterator, Tuple
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


@dataclass
class Entry:
    """Internal representation of a directory entry."""

    path: str
    is_dir: bool
    is_symlink: bool


def _to_entry(os_entry: DirEntry[str], rel_dir: str) -> Entry:
    rel_path = os.path.join(rel_dir, os_entry.name)
    return Entry(rel_path, os_entry.is_dir(), os_entry.is_symlink())


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


def _skip_entry(
    entry: Entry,
    config: Configuration,
    git_ignore: Union[Callable[[str], bool], None] = None,
    flags: Flags = Flags(),
) -> bool:
    skip_conditions = [
        (not flags.follow_symlinks and entry.is_symlink),
        (not flags.include_hidden and entry.path.startswith(".")),
        (entry.path == ".gitignore" and not entry.is_dir),
        (entry.path == ".git" and entry.is_dir),
        (git_ignore and git_ignore(entry.path)),
        (entry.is_dir and rel_dir_to_map_dir(entry.path) in config.directory_map),
        (entry.path == config.configuration_file_name),
    ]

    for condition in skip_conditions:
        if condition:
            if flags.verbose:
                print(f"Skipping {entry.path}")
            return True

    return False


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

        if _skip_entry(entry, config, git_ignore, flags):
            continue

        for idx in _get_matching_item_index(
            backlog,
            entry.path,
            os_entry.is_dir(),
            flags.verbose,
        ):
            backlog_entry = backlog[idx]
            backlog_entry.count += 1
            if flags.verbose:
                print(f"  Registered usage for path {entry.path}")

            if os_entry.is_dir():
                _handle_use_rule(
                    backlog, backlog_entry.use_rule, config, flags, entry.path
                )
                _handle_if_exists(backlog, backlog_entry, entry.path, flags)

                _fail_if_invalid_repo_structure_recursive(
                    repo_root, entry.path, config, backlog, flags
                )


def _map_dir_to_entry_backlog(
    config: Configuration,
    map_dir: str,
) -> StructureRuleList:

    def _get_use_rules_for_directory(c: Configuration, directory: str) -> List[str]:
        d = rel_dir_to_map_dir(directory)
        return c.directory_map[d]

    use_rules = _get_use_rules_for_directory(config, map_dir)
    return _build_active_entry_backlog(use_rules, map_dir, config)


def assert_full_repository_structure(
    repo_root: str,
    config: Configuration,
    flags: Optional[Flags] = Flags(),
) -> None:
    """Fail if the repo structure directory is invalid given the configuration."""
    assert repo_root is not None

    if "/" not in config.directory_map:
        raise MissingMappingError("Config does not have a root mapping")

    for map_dir in config.directory_map:
        rel_dir = map_dir_to_rel_dir(map_dir)
        backlog = _map_dir_to_entry_backlog(config, rel_dir)

        _fail_if_invalid_repo_structure_recursive(
            repo_root,
            rel_dir,
            config,
            backlog,
            flags or Flags(),
        )
        _fail_if_required_entries_missing(backlog)


def _incremental_path_split(path_to_split: str) -> Iterator[Tuple[str, bool]]:
    """Split the path into incremental tokens.

    Each token starts with the top-level directory and grows the path by
    one directory with each iteration.

    For example:
    path/to/file will return the following listing
    [
      ("path", true),
      ("path/to", true),
      ("path/to/file", false),
    ]
    """
    parts = path_to_split.strip("/").split("/")
    for i in range(len(parts)):
        incremental_path = "/".join(parts[: i + 1])
        is_directory = i < len(parts) - 1
        yield incremental_path, is_directory


def _assert_path_in_backlog(
    backlog: StructureRuleList, config: Configuration, flags: Flags, path: str
):

    for sub_path, is_dir in _incremental_path_split(path):
        if _skip_entry(Entry(sub_path, is_dir, is_symlink=False), config, flags=flags):
            return

        for idx in _get_matching_item_index(
            backlog,
            sub_path,
            is_dir,
            flags.verbose,
        ):
            if flags.verbose:
                print(f"  Found match path {sub_path}")

            if is_dir:
                _handle_use_rule(
                    backlog, backlog[idx].use_rule, config, flags, sub_path
                )
                _handle_if_exists(backlog, backlog[idx], sub_path, flags)

            if flags.verbose:
                print(f"Found entry in backlog with index {idx}")


def assert_path(
    config: Configuration,
    path: str,
    flags: Flags,
) -> None:
    """Fail if the given path is invalid according to the configuration.

    Note that this function will not be able to ensure if all required
    entries are present."""

    def _get_corresponding_map_dir(c: Configuration, f: Flags, p: str):

        map_dir = ""
        for sub_path, is_dir in _incremental_path_split(p):
            map_sub_dir = rel_dir_to_map_dir(sub_path)
            if is_dir and map_sub_dir in c.directory_map:
                map_dir = map_sub_dir

        if f.verbose:
            print(f"Found corresponding map dir for {p}: {map_dir}")

        return map_dir

    backlog = _map_dir_to_entry_backlog(
        config, map_dir_to_rel_dir(_get_corresponding_map_dir(config, flags, path))
    )

    _assert_path_in_backlog(backlog, config, flags, path)
