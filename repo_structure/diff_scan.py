"""Library functions for repo structure directory verification."""

import logging
from dataclasses import replace
from pathlib import Path
from typing import Iterator

from .config import (
    Configuration,
)

from .models import (
    Entry,
    Flags,
    MatchFailure,
    MatchFailureCode,
    ScanIssue,
    ScanResult,
    StructureRuleList,
)
from .paths import (
    join_path_normalized,
    map_dir_to_rel_dir,
    normalize_path,
    rel_dir_to_map_dir,
)
from .scanning import (
    check_companion_files,
    expand_if_exists,
    expand_use_rule,
    get_matching_item_index,
    map_dir_to_entry_backlog,
    skip_entry,
)

_LOGGER = logging.getLogger(__name__)

_MATCH_FAILURE_LABEL: dict[MatchFailureCode, str] = {
    "forbidden_entry": "Forbidden",
    "unspecified_entry": "Unspecified",
}


class DiffScanProcessor:
    """Handles differential scanning of specific paths with stateful configuration."""

    def __init__(
        self,
        config: Configuration,
        flags: Flags | None = None,
        repo_root: str = ".",
    ):
        """Initialize the diff scanner with static configuration.

        Args:
            config: Repository structure configuration
            flags: Scanning flags (verbose, follow_symlinks, include_hidden)
            repo_root: Root directory the checked paths are relative to.
                Defaults to the process CWD, which is what the pre-commit hook
                and the CLI pass paths relative to.
        """
        self.config = config
        self.flags = flags if flags is not None else Flags()
        self.repo_root = repo_root
        self.config_file_names = config.configuration_file_names_for(repo_root)

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
        self,
        backlog: StructureRuleList,
        rel_path: str,
        original_path: str,
        map_dir: str,
    ) -> ScanIssue | None:
        """Check if path is valid in backlog and return ScanIssue if invalid.

        Args:
            backlog: List of structure rules to check against
            rel_path: Path to check, relative to the map dir
            original_path: Path as given to `check_path`, used for reporting
            map_dir: Map dir `rel_path` is relative to, used for reporting
        """
        base_dir = map_dir_to_rel_dir(map_dir)
        for rel_dir, entry_name, is_dir in self._incremental_path_split(rel_path):
            if skip_entry(
                Entry(
                    path=entry_name, rel_dir=rel_dir, is_dir=is_dir, is_symlink=False
                ),
                self.config.directory_map,
                self.config_file_names,
                flags=self.flags,
            ):
                return None

            match_result = get_matching_item_index(
                backlog,
                entry_name,
                is_dir,
                self.flags.verbose,
            )

            if isinstance(match_result, MatchFailure):
                return ScanIssue(
                    severity="error",
                    code=match_result.code,
                    message=(
                        f"{_MATCH_FAILURE_LABEL[match_result.code]} entry "
                        f"'{original_path}' found. Map dir: '{map_dir}'"
                    ),
                    path=original_path,
                )

            _LOGGER.debug("  Found match for path '%s'", entry_name)

            # Check for required companion files
            backlog_match = backlog[match_result.index]

            # Construct full directory path by combining base_dir and rel_dir
            full_rel_dir = (
                join_path_normalized(base_dir, rel_dir) if base_dir else rel_dir
            )
            companion_issue = check_companion_files(
                entry_name,
                backlog_match,
                str(Path(self.repo_root) / full_rel_dir),
                self.flags.verbose,
            )
            if companion_issue:
                # The companion check only knows the entry name; report the
                # path the caller asked about.
                return replace(companion_issue, path=original_path)

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

        _LOGGER.debug("Found corresponding map dir for '%s': '%s'", path, map_dir)

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
        base_dir = map_dir_to_rel_dir(map_dir)
        backlog = map_dir_to_entry_backlog(
            self.config.directory_map,
            self.config.structure_rules,
            base_dir,
        )
        if not backlog:
            _LOGGER.debug("backlog empty - returning success")
            return None

        rel_path = str(Path(path).relative_to(base_dir)) if base_dir else path
        return self._check_path_in_backlog(backlog, rel_path, path, map_dir)

    def check_paths(self, paths: list[str]) -> ScanResult:
        """Check multiple paths efficiently using the same configuration.

        Args:
            paths: List of paths to check

        Returns:
            ScanResult holding one error per invalid path. A diff scan cannot
            detect missing required entries, so warnings are always empty.
        """
        errors = []
        for path in paths:
            issue = self.check_path(path)
            if issue:
                errors.append(issue)
        return ScanResult(errors=errors)
