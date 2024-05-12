"""Library functions for repo structure directory verification."""

import os
import re
from dataclasses import dataclass, field
from typing import List

from repo_structure_config import Configuration


# Exception for missing mapping
class MissingMappingError(Exception):
    """Exception raised when no directory mapping available for entry."""


class MissingRequiredEntriesError(Exception):
    """Exception raised when required entries are missing."""


@dataclass
class TokenRequiredOptional:
    """Collecting required and optional entries for convenience."""

    required: List[re.Pattern] = field(default_factory=list)
    optional: List[re.Pattern] = field(default_factory=list)


# data class for directory tokens (files/directories) separated by optional and required tokens
@dataclass
class TokenSets:
    """Collecting files and dirs for convenience."""

    files: TokenRequiredOptional = field(default_factory=TokenRequiredOptional)
    dirs: TokenRequiredOptional = field(default_factory=TokenRequiredOptional)


def _rel_to_map_dir(input_dir: str):
    return os.path.join("/", input_dir)


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


def _get_active_token_sets(
    active_use_rules: List[str], config: Configuration
) -> TokenSets:
    result = TokenSets()
    for rule in active_use_rules:
        result.files.required.extend(config.structure_rules[rule].required.files)
        result.files.optional.extend(config.structure_rules[rule].optional.files)
        result.dirs.required.extend(config.structure_rules[rule].required.directories)
        result.dirs.optional.extend(config.structure_rules[rule].optional.directories)
    return result


def _from_dir_to_token_sets(
    config: Configuration,
    map_dir: str,
) -> TokenSets:
    use_rules = _get_use_rules_for_directory(config, map_dir)
    return _get_active_token_sets(use_rules, config)


def _remove_if_present(items: List[re.Pattern], needle: str) -> List[re.Pattern]:
    if re.compile(needle) in items:
        items.remove(re.compile(needle))
    elif any(pattern.match(needle) for pattern in items):
        items = [pattern for pattern in items if not pattern.match(needle)]
    return items


def _fail_if_required_entries_missing(token_set: TokenSets) -> None:
    if len(token_set.files.required) > 0 or len(token_set.dirs.required) > 0:
        message = "Required entries missing: \nFiles:"
        for f in token_set.files.required:
            message += f"\n\t{f.pattern}"
        message += "\nDirs:"
        for d in token_set.dirs.required:
            message += f"\n\t{d.pattern}"
        raise MissingRequiredEntriesError(message)


def _fail_if_invalid_repo_structure_recursive(
    dir_to_check: str, config: Configuration, token_set: TokenSets
) -> None:
    for root, dirs, files in os.walk(dir_to_check):
        rel_dir = os.path.relpath(root, dir_to_check)
        if rel_dir == ".":
            rel_dir = ""

        for f in files:
            file_path = os.path.join(rel_dir, f)
            token_set.files.required = _remove_if_present(
                token_set.files.required, file_path
            )

        for d in dirs:
            dir_path = os.path.join(rel_dir, d)
            token_set.dirs.required = _remove_if_present(
                token_set.dirs.required, dir_path
            )
            if _rel_to_map_dir(dir_path) in config.directory_mappings:
                _fail_if_invalid_repo_structure_recursive(
                    os.path.join(dir_to_check, dir_path),
                    config,
                    _from_dir_to_token_sets(config, _rel_to_map_dir(dir_path)),
                )

    _fail_if_required_entries_missing(token_set)


def fail_if_invalid_repo_structure(
    dir_to_check: "str | None", config: Configuration
) -> None:
    """Fail if the repo structure directory is invalid according to the configuration."""
    if dir_to_check is None:
        return

    # start with repo root
    map_dir = "/"

    _fail_if_invalid_repo_structure_recursive(
        dir_to_check, config, _from_dir_to_token_sets(config, map_dir)
    )
