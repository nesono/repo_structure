"""Library functions for repo structure directory verification."""

# pylint: disable=import-error

import os

from typing import List, Callable, Union
from gitignore_parser import parse_gitignore

from .repo_structure_config import (
    Configuration,
)

from .repo_structure_lib import (
    map_dir_to_rel_dir,
    _skip_entry,
    _to_entry,
    _get_matching_item_index,
    _handle_use_rule,
    _handle_if_exists,
    _map_dir_to_entry_backlog,
    StructureRuleList,
    Flags,
    UnspecifiedEntryError,
    ForbiddenEntryError,
)


# Exception for missing mapping
class MissingMappingError(Exception):
    """Exception raised when no directory mapping available for entry."""


class MissingRequiredEntriesError(Exception):
    """Exception raised when required entries are missing."""


class EntryTypeMismatchError(Exception):
    """Exception raised when unspecified entry type is not matching the found entry."""


def _fail_if_required_entries_missing(
    rel_dir: str,
    entry_backlog: StructureRuleList,
) -> None:

    def _report_missing_entries(
        missing_files: List[str], missing_dirs: List[str]
    ) -> str:
        result = f"Required patterns missing in  directory '{rel_dir}':\n"
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

        if _skip_entry(
            entry,
            config.directory_map,
            config.configuration_file_name,
            git_ignore,
            flags,
        ):
            continue

        try:
            indices = _get_matching_item_index(
                backlog,
                entry.path,
                os_entry.is_dir(),
                flags.verbose,
            )
        except UnspecifiedEntryError as err:
            raise UnspecifiedEntryError(
                f"Unspecified entry found: '{entry.rel_dir}/{entry.path}'"
            ) from err
        except ForbiddenEntryError as err:
            raise ForbiddenEntryError(
                f"Forbidden entry found: '{entry.rel_dir}/{entry.path}'"
            ) from err

        for idx in indices:
            backlog_entry = backlog[idx]
            backlog_entry.count += 1

            if os_entry.is_dir():
                new_backlog: StructureRuleList = []
                _handle_use_rule(
                    new_backlog,
                    backlog_entry.use_rule,
                    config.structure_rules,
                    flags,
                    entry.path,
                )
                _handle_if_exists(new_backlog, backlog_entry, flags)

                _fail_if_invalid_repo_structure_recursive(
                    repo_root,
                    os.path.join(rel_dir, entry.path),
                    config,
                    new_backlog,
                    flags,
                )
                _fail_if_required_entries_missing(
                    os.path.join(rel_dir, entry.path), new_backlog
                )


def _process_map_dir(
    map_dir: str, repo_root: str, config: Configuration, flags: Flags = Flags()
):
    """Process a single map directory entry."""
    rel_dir = map_dir_to_rel_dir(map_dir)
    backlog = _map_dir_to_entry_backlog(
        config.directory_map, config.structure_rules, rel_dir
    )

    if not backlog:
        if flags.verbose:
            print("backlog empty - returning success")
        return

    _fail_if_invalid_repo_structure_recursive(
        repo_root,
        rel_dir,
        config,
        backlog,
        flags,
    )
    _fail_if_required_entries_missing(rel_dir, backlog)


def assert_full_repository_structure(
    repo_root: str,
    config: Configuration,
    flags: Flags = Flags(),
) -> None:
    """Fail if the repo structure directory is invalid given the configuration."""
    assert repo_root is not None

    if "/" not in config.directory_map:
        raise MissingMappingError("Config does not have a root mapping")

    for map_dir in config.directory_map:
        _process_map_dir(map_dir, repo_root, config, flags)
