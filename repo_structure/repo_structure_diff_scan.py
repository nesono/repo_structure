"""Library functions for repo structure directory verification."""

import os

from typing import Iterator

from .repo_structure_config import (
    Configuration,
)

from .repo_structure_lib import (
    rel_dir_to_map_dir,
    map_dir_to_rel_dir,
    skip_entry,
    Entry,
    expand_use_rule,
    expand_if_exists,
    Flags,
    map_dir_to_entry_backlog,
    StructureRuleList,
    normalize_path,
    join_path_normalized,
    ScanIssue,
    get_matching_item_index,
    check_companion_files,
)


class DiffScanProcessor:
    """Handles differential scanning of specific paths with stateful configuration."""

    def __init__(self, config: Configuration, flags: Flags = Flags()):
        """Initialize the diff scanner with static configuration.

        Args:
            config: Repository structure configuration
            flags: Scanning flags (verbose, follow_symlinks, include_hidden)
        """
        self.config = config
        self.flags = flags

    def _incremental_path_split(
        self, path_to_split: str
    ) -> Iterator[tuple[str, str, bool]]:
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
        # Normalize path separators for cross-platform compatibility
        normalized_path = normalize_path(path_to_split)
        parts = normalized_path.strip("/").split("/")
        for i, part in enumerate(parts):
            rel_dir = "/".join(parts[:i])
            is_directory = i < len(parts) - 1
            yield rel_dir, part, is_directory

    def _check_path_in_backlog(
        self, backlog: StructureRuleList, path: str
    ) -> ScanIssue | None:
        """Check if path is valid in backlog and return ScanIssue if invalid."""
        for rel_dir, entry_name, is_dir in self._incremental_path_split(path):
            if skip_entry(
                Entry(
                    path=entry_name, rel_dir=rel_dir, is_dir=is_dir, is_symlink=False
                ),
                self.config.directory_map,
                self.config.configuration_file_name,
                flags=self.flags,
            ):
                return None

            match_result = get_matching_item_index(
                backlog,
                entry_name,
                is_dir,
                self.flags.verbose,
            )

            if not match_result.success:
                return match_result.issue

            if self.flags.verbose:
                print(f"  Found match for path '{entry_name}'")

            # Check for required companion files
            idx = match_result.index
            assert idx is not None  # Type hint for mypy
            backlog_match = backlog[idx]

            companion_issue = check_companion_files(
                entry_name, backlog_match, rel_dir, self.flags.verbose
            )
            if companion_issue:
                return companion_issue

            if is_dir:
                backlog = expand_use_rule(
                    backlog_match.use_rule,
                    self.config.structure_rules,
                    self.flags,
                    entry_name,
                ) or expand_if_exists(backlog_match, self.flags)

        return None

    def _get_corresponding_map_dir(self, path: str) -> str:
        """Get the corresponding map directory for the given path."""
        map_dir = "/"
        for rel_dir, entry_name, is_dir in self._incremental_path_split(path):
            map_sub_dir = rel_dir_to_map_dir(join_path_normalized(rel_dir, entry_name))
            if is_dir and map_sub_dir in self.config.directory_map:
                map_dir = map_sub_dir

        if self.flags.verbose:
            print(f"Found corresponding map dir for '{path}': '{map_dir}'")

        return map_dir

    def check_path(self, path: str) -> ScanIssue | None:
        """Check if the given path is valid according to the configuration.

        Args:
            path: Path to check

        Returns:
            ScanIssue if invalid, None if valid.
            Note that this function will not be able to ensure if all required
            entries are present.
        """
        map_dir = self._get_corresponding_map_dir(path)
        backlog = map_dir_to_entry_backlog(
            self.config.directory_map,
            self.config.structure_rules,
            map_dir_to_rel_dir(map_dir),
        )
        if not backlog:
            if self.flags.verbose:
                print("backlog empty - returning success")
            return None

        rel_path = os.path.relpath(path, map_dir_to_rel_dir(map_dir))
        issue = self._check_path_in_backlog(backlog, rel_path)
        if issue:
            # Update the message to include the original path and map_dir context
            if issue.code == "unspecified_entry":
                issue.message = (
                    f"Unspecified entry '{path}' found. Map dir: '{map_dir}'"
                )
            elif issue.code == "forbidden_entry":
                issue.message = f"Forbidden entry '{path}' found. Map dir: '{map_dir}'"
            issue.path = path

        return issue

    def check_paths(self, paths: list[str]) -> list[ScanIssue]:
        """Check multiple paths efficiently using the same configuration.

        Args:
            paths: List of paths to check

        Returns:
            List of ScanIssues for invalid paths. Empty list if all paths are valid.
        """
        issues = []
        for path in paths:
            issue = self.check_path(path)
            if issue:
                issues.append(issue)
        return issues
