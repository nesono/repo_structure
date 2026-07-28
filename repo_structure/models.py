"""Data types shared across repo_structure."""

import re
from dataclasses import dataclass, field
from typing import Final, Literal

IGNORE_RULE: Final = "ignore"
BUILTIN_DIRECTORY_RULES: Final = (IGNORE_RULE,)


@dataclass
class RepoEntry:  # pylint: disable=too-many-instance-attributes
    """Wrapper for entries in the directory structure, that store the path
    as a string together with the entry type."""

    path: re.Pattern
    is_dir: bool
    is_required: bool
    is_forbidden: bool
    use_rule: str = ""
    if_exists: list["RepoEntry"] = field(default_factory=list)
    companion: list["RepoEntry"] = field(default_factory=list)
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


DirectoryMap = dict[str, list[str]]
StructureRuleList = list[RepoEntry]
StructureRuleMap = dict[str, StructureRuleList]


@dataclass
class ScanIssue:
    """Represents a single finding from a scan.

    severity: "error" or "warning"
    code: short machine-consumable code (e.g., "unused_structure_rule")
    message: human-readable description
    path: optional path context for the issue
    """

    severity: Literal["error", "warning"]
    code: str
    message: str
    path: str | None = None


@dataclass
class ScanResult:
    """Outcome of a scan: the issues found, split by severity.

    Both processors return this shape so callers do not have to special-case
    per-processor return types.
    """

    errors: list[ScanIssue] = field(default_factory=list)
    warnings: list[ScanIssue] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        """True when the scan found no errors. Warnings do not fail a scan."""
        return not self.errors


@dataclass(frozen=True)
class MatchSuccess:
    """Successful match: holds the index of the matched backlog entry."""

    index: int


@dataclass(frozen=True)
class MatchFailure:
    """Failed match: holds the resulting ScanIssue."""

    issue: ScanIssue


MatchResult = MatchSuccess | MatchFailure
