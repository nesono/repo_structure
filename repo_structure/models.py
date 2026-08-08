"""Data types shared across repo_structure."""

import re
from dataclasses import dataclass, field
from typing import Final, Literal

IGNORE_RULE: Final = "ignore"
BUILTIN_DIRECTORY_RULES: Final = (IGNORE_RULE,)


@dataclass
class RepoEntry:
    """Wrapper for entries in the directory structure, that store the path
    as a string together with the entry type.

    Owned by the parsed configuration and shared by every scan, so it holds no
    scan state -- see :class:`BacklogEntry`.
    """

    path: re.Pattern
    is_dir: bool
    is_required: bool
    is_forbidden: bool
    use_rule: str = ""
    if_exists: list["RepoEntry"] = field(default_factory=list)
    companion: list["RepoEntry"] = field(default_factory=list)


@dataclass
class BacklogEntry:
    """One entry of the backlog a scan builds for a single directory.

    Wrapping rather than copying the :class:`RepoEntry` keeps the match counter
    -- the only mutable state a scan keeps -- off the configuration, so two
    directories governed by the same rule cannot see each other's counts.

    ``is_required`` is carried here rather than read off ``entry`` because a
    companion pattern joins the backlog as optional even when the rule declares
    it required: it is enforced against the file that names it, not against the
    directory as a whole.
    """

    entry: RepoEntry
    is_required: bool
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
Backlog = list[BacklogEntry]
"""The entries a scan checks one directory against, with their match counts."""

INHERIT_ALL: Final = "all"


@dataclass
class InheritSpec:
    """What a configuration takes over from the configuration that mounted it.

    ``structure_rules`` is either :data:`INHERIT_ALL`, an explicit list of rule
    names, or None when the configuration inherits nothing. ``override`` names
    the inherited rules the configuration deliberately redefines; redefining an
    inherited rule that is not listed here is an error.
    """

    structure_rules: str | list[str] | None = None
    override: list[str] = field(default_factory=list)

    @property
    def inherits_everything(self) -> bool:
        """True if the configuration asked for every parent structure rule."""
        return self.structure_rules == INHERIT_ALL


@dataclass
class ParsedDocument:
    """One configuration document, parsed but not yet merged with others.

    Rule names are still exactly as written in the document -- qualification
    into the merged namespace happens during the merge, not here. Likewise,
    ``directory_map`` keys are relative to the document's own directory.
    """

    structure_rules: StructureRuleMap = field(default_factory=dict)
    structure_rule_descriptions: dict[str, str] = field(default_factory=dict)
    directory_map: DirectoryMap = field(default_factory=dict)
    directory_descriptions: dict[str, str] = field(default_factory=dict)
    mounts: dict[str, str] = field(default_factory=dict)
    inherit: InheritSpec = field(default_factory=InheritSpec)


@dataclass
class ConfigurationData:
    """Stores configuration data.

    This is the flattened result of merging every configuration document that
    took part in a load. Rules contributed by a mounted configuration are keyed
    by their qualified name (see ``config_merge.qualify``); ``rule_origins``
    maps each rule back to the configuration file that defined it.
    """

    structure_rules: StructureRuleMap = field(default_factory=dict)
    directory_map: DirectoryMap = field(default_factory=dict)
    configuration_file_name: str = ""
    structure_rule_descriptions: dict[str, str] = field(default_factory=dict)
    directory_descriptions: dict[str, str] = field(default_factory=dict)
    configuration_file_names: set[str] = field(default_factory=set)
    rule_origins: dict[str, str] = field(default_factory=dict)

    def get_structure_rule_description(self, rule_name: str) -> str:
        """Get the description for a structure rule."""
        return self.structure_rule_descriptions.get(rule_name, "")

    def get_directory_description(self, directory: str) -> str:
        """Get the description for a directory."""
        return self.directory_descriptions.get(directory, "")


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


MatchFailureCode = Literal["forbidden_entry", "unspecified_entry"]


@dataclass(frozen=True)
class MatchFailure:
    """Failed match: why it failed and which entry caused it.

    Deliberately carries no message. Only the caller knows the path and
    map-dir context a message should mention, so each processor builds the
    final ScanIssue itself instead of patching one built here.
    """

    code: MatchFailureCode
    entry_path: str
    is_dir: bool


MatchResult = MatchSuccess | MatchFailure
