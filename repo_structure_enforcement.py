"""Library functions for repo structure directory verification."""

# pylint: disable=import-error
import os
import re
from os import DirEntry
from dataclasses import dataclass

from typing import List, Callable, Generator, Optional
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
) -> Generator[int, None, None]:
    was_found = False
    for i, v in enumerate(items):
        if verbose:
            print(f"  Matching against {v.path}")
        if v.path.fullmatch(needle) and v.entry_type == entry_type:
            if verbose:
                print(f"  Found match at index {i}, yielding")
            was_found = True
            yield i
    if not was_found:
        raise UnspecifiedEntryError(f"Found unspecified entry: {needle}")


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
    backlog: List[DirectoryEntryWrapper],
    flags: Flags,
) -> None:
    git_ignore = _get_git_ignore(repo_root)

    # go through all the files in the repository
    for entry in os.scandir(os.path.join(repo_root, rel_dir)):
        rel_path = os.path.join(rel_dir, entry.name)
        if flags.verbose:
            print(f"Checking file {rel_path}")

        if _skip_entry(entry, rel_path, config, git_ignore, flags):
            continue

        # go through all found matches in the entry_backlog
        for idx in _get_matching_item_index(
            backlog,
            rel_path,
            EntryType.DIR if entry.is_dir() else EntryType.FILE,
            flags.verbose,
        ):
            backlog_entry = backlog[idx]
            backlog_entry.count += 1
            if flags.verbose:
                print(f"  Registered usage for path {rel_path}")

            if entry.is_dir():
                _handle_use_rule(backlog, backlog_entry, config, flags, rel_path)

                # enter the subdirectory recursively
                _fail_if_invalid_repo_structure_recursive(
                    repo_root, rel_path, config, backlog, flags
                )


def _handle_use_rule(backlog, backlog_entry, config, flags, rel_path):
    if backlog_entry.use_rule:
        if flags.verbose:
            print(f"use_rule found for rel path {rel_path}")
        backlog.extend(
            _build_active_entry_backlog(
                [backlog_entry.use_rule],
                rel_path,
                config,
            )
        )


def _get_git_ignore(repo_root: str) -> Callable[[str], bool] | None:
    git_ignore_path = os.path.join(repo_root, ".gitignore")
    if os.path.isfile(git_ignore_path):
        return parse_gitignore(git_ignore_path)
    return None


def _skip_entry(
    entry: DirEntry[str],
    rel_path: str,
    config: Configuration,
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

    if entry.is_dir():
        map_dir = _rel_dir_to_map_dir(rel_path)
        if map_dir in config.directory_mappings:
            if flags.verbose:
                print(f"Overlapping directory mappings found: {rel_path} - skipping")
            return True

    return False


def fail_if_invalid_repo_structure(
    repo_root: str,
    config: Configuration,
    flags: Optional[Flags] = Flags(),
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
