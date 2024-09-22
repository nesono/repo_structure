"""Library functions for repo structure directory verification."""

# pylint: disable=import-error
import os
import re
from os import DirEntry
from dataclasses import dataclass

from typing import List, Callable
from gitignore_parser import parse_gitignore

from repo_structure_config import (
    Configuration,
    ContentRequirement,
    DirectoryEntryWrapper,
    EntryType,
)


@dataclass
class Flags:
    """Flags for common parsing config settings."""

    follow_symlinks: bool = False
    include_hidden: bool = False
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


def _rel_dir_to_map_dir(rel_dir: str):
    if not rel_dir or rel_dir == "/":
        return "/"

    if not rel_dir.startswith("/"):
        rel_dir = "/" + rel_dir
    if not rel_dir.endswith("/"):
        rel_dir = rel_dir + "/"

    return rel_dir


def _map_dir_to_rel_dir(map_dir: str) -> str:
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
    items: List[DirectoryEntryWrapper],
    needle: str,
    entry_type: EntryType,
    verbose: bool = False,
) -> int | None:
    for i, v in enumerate(items):
        if verbose:
            print(f"  Matching against {v.path}")
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
        if (
            entry.content_requirement == ContentRequirement.REQUIRED
            and entry.count == 0
        ):
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
    flags: Flags,
) -> None:
    git_ignore = _get_git_ignore(repo_root)

    for entry in os.scandir(os.path.join(repo_root, rel_dir)):
        if flags.verbose:
            print(f"Checking file {entry.path}")

        # TODO(ji): make this flexible, i.e. when a file is specified in the config,
        # test against it anyways no matter if it's in gitignore or hidden, or symlink?

        rel_path = os.path.join(rel_dir, entry.name)
        entry_type = EntryType.DIR if entry.is_dir() else EntryType.FILE
        idx = _get_matching_item_index(
            entry_backlog, rel_path, entry_type, flags.verbose
        )

        if idx is None:
            if _skip_entry(entry, git_ignore, flags):
                continue
            raise UnspecifiedEntryError(f"Found unspecified entry: {rel_path}")

        if entry.is_file():
            _process_file_entry(entry, entry_backlog, idx, rel_path, flags.verbose)

        elif entry.is_dir():
            if entry_backlog[idx].entry_type != EntryType.DIR:
                raise EntryTypeMismatchError(f"Directory {rel_path} matches file")

            if _skip_entry_mapping(rel_path, config, flags.verbose):
                entry_backlog[idx].count += 1
                continue

            if _skip_entry(entry, git_ignore, flags):
                continue

            new_rules = _handle_use_rule(entry_backlog[idx], rel_path, config)
            entry_backlog[idx].count += 1
            entry_backlog.extend(new_rules)

            # enter the subdirectory
            _fail_if_invalid_repo_structure_recursive(
                repo_root, rel_path, config, entry_backlog, flags
            )


def _get_git_ignore(repo_root: str) -> Callable[[str], bool] | None:
    git_ignore_path = os.path.join(repo_root, ".gitignore")
    if os.path.isfile(git_ignore_path):
        return parse_gitignore(git_ignore_path)
    return None


def _skip_entry(
    entry: DirEntry[str],
    git_ignore: Callable[[str], bool] | None = None,
    flags: Flags = Flags(),
) -> bool:
    if git_ignore and git_ignore(entry.path):
        if flags.verbose:
            print(".gitignore matched, skipping")
        return True

    if not flags.follow_symlinks and entry.is_symlink():
        if flags.verbose:
            print("Symlink found, skipping")
        return True

    if not flags.include_hidden and entry.name.startswith("."):
        if flags.verbose:
            print("Hidden file found, skipping")
        return True

    return False


def _process_file_entry(
    entry: os.DirEntry[str],
    entry_backlog: List[DirectoryEntryWrapper],
    idx: int,
    rel_path: str,
    verbose: bool,
) -> None:
    if entry_backlog[idx].entry_type != EntryType.FILE:
        raise EntryTypeMismatchError(f"File {rel_path} matches directory")
    if verbose:
        print(f"Matched file {entry.path}")
    entry_backlog[idx].count += 1


def _skip_entry_mapping(rel_path: str, config: Configuration, verbose: bool) -> bool:
    if _rel_dir_to_map_dir(rel_path) in config.directory_mappings:
        if verbose:
            print(f"Matched directory {rel_path}")
        return True
    return False


def _handle_use_rule(
    entry: DirectoryEntryWrapper,
    rel_path: str,
    config: Configuration,
) -> List[DirectoryEntryWrapper]:
    new_rules = []
    if entry.use_rule:
        new_rules.extend(
            _build_active_entry_backlog(
                [entry.use_rule],
                rel_path,
                config,
            )
        )
    return new_rules


def fail_if_invalid_repo_structure(
    repo_root: str,
    config: Configuration,
    flags: Flags,
) -> None:
    """Fail if the repo structure directory is invalid given the configuration."""
    if repo_root is None:
        if flags.verbose:
            print("repo_root is None, returning early")
        return

    # ensure root mapping is there
    if "/" not in config.directory_mappings:
        raise MissingMappingError("Config does not have a root mapping")

    for map_dir in config.directory_mappings:
        rel_dir = _map_dir_to_rel_dir(map_dir)
        entry_backlog = _map_dir_to_entry_backlog(config, rel_dir)

        # parse directory and burn down entry_backlog
        _fail_if_invalid_repo_structure_recursive(
            repo_root,
            rel_dir,
            config,
            entry_backlog,
            flags,
        )
        # report non-empty entry_backlog
        _fail_if_required_entries_missing(entry_backlog)
