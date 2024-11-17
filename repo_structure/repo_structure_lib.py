"""Common library code for repo_structure."""

import os
import re
from dataclasses import dataclass, field, replace
from os import DirEntry
from typing import List, Union, Callable, Dict, Final

BUILTIN_DIRECTORY_RULES: Final = ["ignore"]


class UnspecifiedEntryError(Exception):
    """Exception raised when unspecified entries are found."""


class StructureRuleError(Exception):
    """Structure rule related error."""


class UseRuleError(Exception):
    """Use_rule related error."""


class TemplateError(Exception):
    """Repo structure template related error."""


class ConfigurationParseError(Exception):
    """Thrown when configuration could not be parsed."""


class ForbiddenEntryError(Exception):
    """Thrown when a forbidden entry is found."""


@dataclass
class RepoEntry:
    """Wrapper for entries in the directory structure, that store the path
    as a string together with the entry type."""

    path: re.Pattern
    is_dir: bool
    is_required: bool
    is_forbidden: bool
    use_rule: str = ""
    if_exists: List["RepoEntry"] = field(default_factory=list)
    count: int = 0


@dataclass
class Entry:
    """Internal representation of a directory entry."""

    path: str
    rel_dir: str
    is_dir: bool
    is_symlink: bool


@dataclass
class Flags:
    """Flags for common parsing config settings."""

    follow_symlinks: bool = False
    include_hidden: bool = True
    verbose: bool = False


DirectoryMap = Dict[str, List[str]]
StructureRuleList = List[RepoEntry]
StructureRuleMap = Dict[str, StructureRuleList]


def rel_dir_to_map_dir(rel_dir: str):
    """Convert a relative directory path to a mapped directory path.

    This function ensures that a given relative directory path conforms to
    a specific format required for mapping. It enforces that the path starts
    and ends with a '/' character.
    """
    if not rel_dir or rel_dir == "/":
        return "/"

    if not rel_dir.startswith("/"):
        rel_dir = "/" + rel_dir
    if not rel_dir.endswith("/"):
        rel_dir = rel_dir + "/"

    return rel_dir


def map_dir_to_rel_dir(map_dir: str) -> str:
    """Convert a mapped directory path to a relative directory path.

    This function takes a mapped directory path and converts it back to
    a relative directory path by removing the leading and trailing '/'
    characters if they exist. If the input is the root directory or empty,
    it returns an empty string.
    """
    if not map_dir or map_dir == "/":
        return ""

    return map_dir[1:-1]


def _skip_entry(
    entry: Entry,
    directory_map: DirectoryMap,
    config_file_name: str,
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
            in directory_map
        ),
        (entry.path == config_file_name),
    ]

    for condition in skip_conditions:
        if condition:
            if flags.verbose:
                print(f"Skipping {entry.path}")
            return True

    return False


def _to_entry(os_entry: DirEntry[str], rel_dir: str) -> Entry:
    return Entry(
        path=os_entry.name,
        rel_dir=rel_dir,
        is_dir=os_entry.is_dir(),
        is_symlink=os_entry.is_symlink(),
    )


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
            if v.is_forbidden:
                raise ForbiddenEntryError(f"Found forbidden entry: {entry_path}")
            result.append(i)
    if len(result) != 0:
        return result

    if is_dir:
        entry_path += "/"
    raise UnspecifiedEntryError(f"Found unspecified entry: {entry_path}")


def _handle_use_rule(
    backlog: StructureRuleList,
    use_rule: str,
    structure_rules: StructureRuleMap,
    flags: Flags,
    rel_path: str,
):
    if use_rule:
        if flags.verbose:
            print(f"use_rule found for rel path {rel_path}")
        backlog.extend(
            _build_active_entry_backlog(
                [use_rule],
                structure_rules,
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


def _map_dir_to_entry_backlog(
    directory_map: DirectoryMap,
    structure_rules: StructureRuleMap,
    map_dir: str,
) -> StructureRuleList:

    def _get_use_rules_for_directory(
        directory_map: DirectoryMap, directory: str
    ) -> List[str]:
        d = rel_dir_to_map_dir(directory)
        return directory_map[d]

    use_rules = _get_use_rules_for_directory(directory_map, map_dir)
    return _build_active_entry_backlog(use_rules, structure_rules)


def _build_active_entry_backlog(
    active_use_rules: List[str], structure_rules: StructureRuleMap
) -> StructureRuleList:
    result: StructureRuleList = []
    for rule in active_use_rules:
        if rule == "ignore":
            continue
        for e in structure_rules[rule]:
            result.append(replace(e, path=re.compile(e.path.pattern)))
    return result
