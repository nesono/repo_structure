"""Library functions for repo structure directory verification."""

# pylint: disable=import-error

import os

from typing import Iterator, Tuple, Optional

from .repo_structure_config import (
    Configuration,
)

from .repo_structure_lib import (
    rel_dir_to_map_dir,
    map_dir_to_rel_dir,
    _skip_entry,
    Entry,
    _get_matching_item_index,
    _handle_use_rule,
    _handle_if_exists,
    Flags,
    _map_dir_to_entry_backlog,
    StructureRuleList,
    UnspecifiedEntryError,
    ForbiddenEntryError,
)

from .repo_structure_full_scan import (
    ScanIssue,
    _get_matching_item_index_safe,
)


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


def _check_path_in_backlog(
    backlog: StructureRuleList, config: Configuration, flags: Flags, path: str
) -> Optional[ScanIssue]:
    """Check if path is valid in backlog and return ScanIssue if invalid."""

    for rel_dir, entry_name, is_dir in _incremental_path_split(path):
        if _skip_entry(
            Entry(path=entry_name, rel_dir=rel_dir, is_dir=is_dir, is_symlink=False),
            config.directory_map,
            config.configuration_file_name,
            flags=flags,
        ):
            return None

        match_result = _get_matching_item_index_safe(
            backlog,
            entry_name,
            is_dir,
            flags.verbose,
        )

        if not match_result.success:
            return match_result.issue

        if flags.verbose:
            print(f"  Found match for path '{entry_name}'")

        if is_dir:
            # At this point we know match_result.index is not None since success is True
            idx = match_result.index
            assert idx is not None  # Type hint for mypy
            backlog_match = backlog[idx]
            backlog = _handle_use_rule(
                backlog_match.use_rule, config.structure_rules, flags, entry_name
            ) or _handle_if_exists(backlog_match, flags)

    return None


def _assert_path_in_backlog(
    backlog: StructureRuleList, config: Configuration, flags: Flags, path: str
):

    for rel_dir, entry_name, is_dir in _incremental_path_split(path):
        if _skip_entry(
            Entry(path=entry_name, rel_dir=rel_dir, is_dir=is_dir, is_symlink=False),
            config.directory_map,
            config.configuration_file_name,
            flags=flags,
        ):
            return

        idx = _get_matching_item_index(
            backlog,
            entry_name,
            is_dir,
            flags.verbose,
        )
        if flags.verbose:
            print(f"  Found match for path '{entry_name}'")

        if is_dir:
            backlog_match = backlog[idx]
            backlog = _handle_use_rule(
                backlog_match.use_rule, config.structure_rules, flags, entry_name
            ) or _handle_if_exists(backlog_match, flags)


def check_path(
    config: Configuration,
    path: str,
    flags: Flags = Flags(),
) -> Optional[ScanIssue]:
    """Check if the given path is valid according to the configuration.

    Returns ScanIssue if invalid, None if valid.
    Note that this function will not be able to ensure if all required
    entries are present."""

    def _get_corresponding_map_dir(c: Configuration, f: Flags, p: str):

        map_dir = "/"
        for rel_dir, entry_name, is_dir in _incremental_path_split(p):
            map_sub_dir = rel_dir_to_map_dir(os.path.join(rel_dir, entry_name))
            if is_dir and map_sub_dir in c.directory_map:
                map_dir = map_sub_dir

        if f.verbose:
            print(f"Found corresponding map dir for '{p}': '{map_dir}'")

        return map_dir

    map_dir = _get_corresponding_map_dir(config, flags, path)
    backlog = _map_dir_to_entry_backlog(
        config.directory_map, config.structure_rules, map_dir_to_rel_dir(map_dir)
    )
    if not backlog:
        if flags.verbose:
            print("backlog empty - returning success")
        return None

    rel_path = os.path.relpath(path, map_dir_to_rel_dir(map_dir))
    issue = _check_path_in_backlog(backlog, config, flags, rel_path)
    if issue:
        # Update the message to include the original path and map_dir context
        if issue.code == "unspecified_entry":
            issue.message = f"Unspecified entry '{path}' found. Map dir: '{map_dir}'"
        elif issue.code == "forbidden_entry":
            issue.message = f"Forbidden entry '{path}' found. Map dir: '{map_dir}'"
        issue.path = path

    return issue


def assert_path(
    config: Configuration,
    path: str,
    flags: Flags = Flags(),
) -> None:
    """Fail if the given path is invalid according to the configuration.

    Note that this function will not be able to ensure if all required
    entries are present."""
    issue = check_path(config, path, flags)
    if issue:
        if issue.code == "unspecified_entry":
            raise UnspecifiedEntryError(issue.message)
        if issue.code == "forbidden_entry":
            raise ForbiddenEntryError(issue.message)
        # Fallback for any other error codes
        raise UnspecifiedEntryError(issue.message)
