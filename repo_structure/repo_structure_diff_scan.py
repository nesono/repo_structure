"""Library functions for repo structure directory verification."""

# pylint: disable=import-error

import os

from typing import Iterator, Tuple

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
            config.directory_map,
            config.configuration_file_name,
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
                    backlog,
                    backlog[idx].use_rule,
                    config.structure_rules,
                    flags,
                    entry_name,
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

    map_dir = _get_corresponding_map_dir(config, flags, path)
    backlog = _map_dir_to_entry_backlog(
        config.directory_map, config.structure_rules, map_dir_to_rel_dir(map_dir)
    )
    if not backlog:
        if flags.verbose:
            print("backlog empty - returning success")
        return

    rel_path = os.path.relpath(path, map_dir_to_rel_dir(map_dir))
    try:
        _assert_path_in_backlog(backlog, config, flags, rel_path)
    except UnspecifiedEntryError as err:
        raise UnspecifiedEntryError(
            f"Unspecified entry {path} found. Map dir: {map_dir}"
        ) from err
    except ForbiddenEntryError as err:
        raise ForbiddenEntryError(
            f"Forbidden entry {path} found. Map dir: {map_dir}"
        ) from err
