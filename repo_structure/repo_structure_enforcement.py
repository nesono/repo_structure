"""Library functions for repo structure directory verification."""

# pylint: disable=import-error

import os
import re
from os import DirEntry
from dataclasses import dataclass, replace

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
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
    jobs: int = 1


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
    active_use_rules: List[str], config: Configuration
) -> StructureRuleList:
    result: StructureRuleList = []
    for rule in active_use_rules:
        for e in config.structure_rules[rule]:
            result.append(replace(e, path=re.compile(e.path.pattern)))
    return result


def _get_matching_item_index(
    backlog: StructureRuleList,
    entry_path: str,
    is_dir: bool,
    verbose: bool = False,
) -> List[int]:
    result: List[int] = []
    for i, v in enumerate(backlog):
        if v.path.fullmatch(entry_path) and v.is_dir == is_dir:
            if verbose:
                print(f"  Found match at index {i}: {v.path.pattern}")
            result.append(i)
    if len(result) != 0:
        return result

    if is_dir:
        entry_path += "/"
    raise UnspecifiedEntryError(f"Found unspecified entry: {entry_path}")


def _fail_if_required_entries_missing(
    entry_backlog: StructureRuleList,
) -> None:

    def _report_missing_entries(
        missing_files: List[str], missing_dirs: List[str]
    ) -> str:
        result = "Matching entries for required patterns missing:\n"
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


@dataclass
class Entry:
    """Internal representation of a directory entry."""

    path: str
    rel_dir: str
    is_dir: bool
    is_symlink: bool


def _to_entry(os_entry: DirEntry[str], rel_dir: str) -> Entry:
    return Entry(
        path=os_entry.name,
        rel_dir=rel_dir,
        is_dir=os_entry.is_dir(),
        is_symlink=os_entry.is_symlink(),
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
                config,
            )
        )


def _handle_if_exists(
    backlog: StructureRuleList, backlog_entry: RepoEntry, flags: Flags
):
    if backlog_entry.if_exists:
        if flags.verbose:
            print(f"if_exists found for rel path {backlog_entry.path.pattern}")
        for e in backlog_entry.if_exists:
            backlog.append(replace(e, path=re.compile(e.path.pattern)))


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
        (
            entry.is_dir
            and rel_dir_to_map_dir(os.path.join(entry.rel_dir, entry.path))
            in config.directory_map
        ),
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

            if os_entry.is_dir():
                new_backlog: StructureRuleList = []
                _handle_use_rule(
                    new_backlog, backlog_entry.use_rule, config, flags, entry.path
                )
                _handle_if_exists(new_backlog, backlog_entry, flags)

                _fail_if_invalid_repo_structure_recursive(
                    repo_root,
                    os.path.join(rel_dir, entry.path),
                    config,
                    new_backlog,
                    flags,
                )
                _fail_if_required_entries_missing(new_backlog)


def _map_dir_to_entry_backlog(
    config: Configuration,
    map_dir: str,
) -> StructureRuleList:

    def _get_use_rules_for_directory(c: Configuration, directory: str) -> List[str]:
        d = rel_dir_to_map_dir(directory)
        return c.directory_map[d]

    use_rules = _get_use_rules_for_directory(config, map_dir)
    return _build_active_entry_backlog(use_rules, config)


def _process_map_dir(
    map_dir: str, repo_root: str, config: Configuration, flags: Optional[Flags]
):
    """Process a single map directory entry."""
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


def assert_full_repository_structure(
    repo_root: str,
    config: Configuration,
    flags: Flags = Flags(),
) -> None:
    """Fail if the repo structure directory is invalid given the configuration."""
    assert repo_root is not None

    if "/" not in config.directory_map:
        raise MissingMappingError("Config does not have a root mapping")

    if flags.jobs == 0:
        flags.jobs = cpu_count()

    if flags.jobs > 1:
        with ProcessPoolExecutor() as executor:
            futures = [
                executor.submit(_process_map_dir, map_dir, repo_root, config, flags)
                for map_dir in config.directory_map
            ]

            # Wait for all tasks to complete
            for future in futures:
                future.result()
    else:
        for map_dir in config.directory_map:
            _process_map_dir(map_dir, repo_root, config, flags)


def _incremental_path_split(path_to_split: str) -> Iterator[Tuple[str, str, bool]]:
    """Split the path into incremental tokens.

    Each token starts with the top-level directory and grows the path by
    one directory with each iteration.

    For example:
    path/to/file will return the following listing
    [
      ("", "path", true),
      ("path", "to", true),
      ("path/to", "file" false),
    ]
    """
    parts = path_to_split.strip("/").split("/")
    for i, part in enumerate(parts):
        rel_dir = "/".join(parts[:i])
        is_directory = i < len(parts) - 1
        yield rel_dir, part, is_directory


def _assert_path_in_backlog(
    backlog: StructureRuleList, config: Configuration, flags: Flags, path: str
):

    for rel_dir, entry_name, is_dir in _incremental_path_split(path):
        if _skip_entry(
            Entry(path=entry_name, rel_dir=rel_dir, is_dir=is_dir, is_symlink=False),
            config,
            flags=flags,
        ):
            return

        for idx in _get_matching_item_index(
            backlog,
            entry_name,
            is_dir,
            flags.verbose,
        ):
            if flags.verbose:
                print(f"  Found match for path {entry_name}")

            if is_dir:
                _handle_use_rule(
                    backlog, backlog[idx].use_rule, config, flags, entry_name
                )
                _handle_if_exists(backlog, backlog[idx], flags)


def assert_path(
    config: Configuration,
    path: str,
    flags: Flags = Flags(),
) -> None:
    """Fail if the given path is invalid according to the configuration.

    Note that this function will not be able to ensure if all required
    entries are present."""

    def _get_corresponding_map_dir(c: Configuration, f: Flags, p: str):

        map_dir = ""
        for rel_dir, entry_name, is_dir in _incremental_path_split(p):
            map_sub_dir = rel_dir_to_map_dir(os.path.join(rel_dir, entry_name))
            if is_dir and map_sub_dir in c.directory_map:
                map_dir = map_sub_dir

        if f.verbose:
            print(f"Found corresponding map dir for {p}: {map_dir}")

        return map_dir

    backlog = _map_dir_to_entry_backlog(
        config, map_dir_to_rel_dir(_get_corresponding_map_dir(config, flags, path))
    )

    _assert_path_in_backlog(backlog, config, flags, path)
