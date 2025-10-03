"""Library functions for repo structure directory verification."""

import os

from typing import Callable
from gitignore_parser import parse_gitignore

from .repo_structure_config import (
    Configuration,
)

from .repo_structure_lib import (
    map_dir_to_rel_dir,
    skip_entry,
    to_entry,
    expand_use_rule,
    expand_if_exists,
    map_dir_to_entry_backlog,
    StructureRuleList,
    Flags,
    join_path_normalized,
    ScanIssue,
    get_matching_item_index,
    check_companion_files,
)


class FullScanProcessor:
    """Handles full repository structure scanning."""

    def __init__(self, repo_root: str, config: Configuration, flags: Flags = Flags()):
        """Initialize the scanner with static configuration.

        Args:
            repo_root: Root directory path being scanned
            config: Repository structure configuration
            flags: Scanning flags (verbose, follow_symlinks, include_hidden)
        """
        self.repo_root = repo_root
        self.config = config
        self.flags = flags
        self.git_ignore = self._get_git_ignore()

    def _get_git_ignore(self) -> Callable[[str], bool] | None:
        """Get gitignore parser, cached for the lifetime of the scan."""
        git_ignore_path = os.path.join(self.repo_root, ".gitignore")
        if os.path.isfile(git_ignore_path):
            return parse_gitignore(git_ignore_path)
        return None

    def _check_required_entries_missing(
        self,
        rel_dir: str,
        entry_backlog: StructureRuleList,
    ) -> ScanIssue | None:

        def _format_missing_entries_message(
            missing_files: list[str], missing_dirs: list[str]
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
            missing_required_dirs = [
                d.path.pattern for d in missing_required if d.is_dir
            ]

            return ScanIssue(
                severity="error",
                code="missing_required_entries",
                message=_format_missing_entries_message(
                    missing_required_files, missing_required_dirs
                ),
                path=rel_dir,
            )
        return None

    def _check_reldir_structure(
        self,
        rel_dir: str,
        backlog: StructureRuleList,
    ) -> list[ScanIssue]:
        """Check repository structure recursively and return list of issues."""
        errors: list[ScanIssue] = []

        entries = self._get_sorted_entries(rel_dir)
        for os_entry in entries:
            entry = to_entry(os_entry, rel_dir)

            if self.flags.verbose:
                print(f"Checking entry {entry.path}")

            if self._should_skip_entry(entry):
                continue

            match_result = get_matching_item_index(
                backlog, entry.path, os_entry.is_dir(), self.flags.verbose
            )

            if not match_result.success:
                self._handle_match_failure(match_result, entry, errors)
                continue

            idx = match_result.index
            assert idx is not None  # Type hint for mypy
            backlog[idx].count += 1

            # Check for required companion files
            companion_issue = check_companion_files(
                entry.path, backlog[idx], rel_dir, self.flags.verbose
            )
            if companion_issue:
                errors.append(companion_issue)

            if os_entry.is_dir():
                errors.extend(self._process_subdirectory(rel_dir, entry, backlog, idx))

        return errors

    def _get_sorted_entries(self, rel_dir: str) -> list[os.DirEntry]:
        dir_path = os.path.join(self.repo_root, rel_dir)
        return sorted(os.scandir(dir_path), key=lambda e: e.name)

    def _should_skip_entry(self, entry) -> bool:
        return skip_entry(
            entry,
            self.config.directory_map,
            self.config.configuration_file_name,
            self.git_ignore,
            self.flags,
        )

    def _handle_match_failure(self, match_result, entry, errors: list[ScanIssue]):
        if match_result.issue:
            match_result.issue.path = join_path_normalized(entry.rel_dir, entry.path)
            errors.append(match_result.issue)

    def _process_subdirectory(
        self,
        rel_dir: str,
        entry,
        backlog: StructureRuleList,
        idx: int,
    ) -> list[ScanIssue]:
        errors: list[ScanIssue] = []
        new_backlog = expand_use_rule(
            backlog[idx].use_rule,
            self.config.structure_rules,
            self.flags,
            entry.path,
        ) or expand_if_exists(backlog[idx], self.flags)

        subdirectory_path = join_path_normalized(rel_dir, entry.path)
        errors.extend(self._check_reldir_structure(subdirectory_path, new_backlog))

        missing_entry_issue = self._check_required_entries_missing(
            subdirectory_path, new_backlog
        )
        if missing_entry_issue:
            errors.append(missing_entry_issue)
        return errors

    def _process_map_dir_sync(self, map_dir: str) -> list[ScanIssue]:
        """Process a single map directory entry and return issues instead of raising exceptions."""
        errors: list[ScanIssue] = []

        rel_dir = map_dir_to_rel_dir(map_dir)
        backlog = map_dir_to_entry_backlog(
            self.config.directory_map, self.config.structure_rules, rel_dir
        )

        if not backlog:
            if self.flags.verbose:
                print("backlog empty - returning success")
            return errors

        # Check repository structure using non-throwing functions
        structure_errors = self._check_reldir_structure(
            rel_dir,
            backlog,
        )
        errors.extend(structure_errors)

        # Check for missing required entries
        missing_entry_issue = self._check_required_entries_missing(rel_dir, backlog)
        if missing_entry_issue:
            errors.append(missing_entry_issue)

        return errors

    def _collect_errors(self) -> list[ScanIssue]:
        errors: list[ScanIssue] = []
        # Missing root mapping error
        if "/" not in self.config.directory_map:
            errors.append(
                ScanIssue(
                    severity="error",
                    code="missing_root_mapping",
                    message="Config does not have a root mapping",
                    path="/",
                )
            )
            # Even if root is missing, we can still attempt warnings computation below
            # but there is nothing to process per-map.
        else:
            # Process each mapped directory independently, collecting errors
            for map_dir in self.config.directory_map:
                map_dir_errors = self._process_map_dir_sync(map_dir)
                errors.extend(map_dir_errors)
        return errors

    def _collect_warnings(self) -> list[ScanIssue]:
        warnings: list[ScanIssue] = []
        used_rules = set()
        for rules in self.config.directory_map.values():
            for r in rules:
                if r and r not in ("ignore",):
                    used_rules.add(r)

        for rule_name in self.config.structure_rules.keys():
            if rule_name not in used_rules:
                warnings.append(
                    ScanIssue(
                        severity="warning",
                        code="unused_structure_rule",
                        message=f"Unused structure rule '{rule_name}'",
                        path=None,
                    )
                )
        return warnings

    def scan(self) -> tuple[list[ScanIssue], list[ScanIssue]]:
        """Scan the repository and return a list of issues (errors and warnings)."""
        errors = self._collect_errors()
        warnings = self._collect_warnings()
        errors.sort(key=lambda x: (x.path is None, x.path or "", x.code))
        warnings.sort(key=lambda x: (x.path is None, x.path or "", x.code))
        return errors, warnings

    def scan_directory(self, map_dir: str) -> list[ScanIssue]:
        """Scan a single directory mapping and return issues.

        Args:
            map_dir: Directory mapping key (e.g. "/", "src/", "tests/")

        Returns:
            List of scan issues found in the specified directory mapping
        """
        return self._process_map_dir_sync(map_dir)
