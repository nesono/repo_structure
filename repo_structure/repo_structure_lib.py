"""Deprecated re-export shim for the former grab-bag common library.

The contents moved into focused modules:

- :mod:`repo_structure.models` — dataclasses, type aliases, rule constants
- :mod:`repo_structure.paths` — path normalization and conversion helpers
- :mod:`repo_structure.patterns` — capture extraction and template substitution
- :mod:`repo_structure.errors` — exception classes
- :mod:`repo_structure.scanning` — entry skipping, matching, backlog building

Import from those modules directly; this shim exists to keep existing imports
working for one release and will be removed afterwards.
"""

from .errors import ConfigurationParseError, StructureRuleError, TemplateError
from .models import (
    BUILTIN_DIRECTORY_RULES,
    IGNORE_RULE,
    DirectoryMap,
    Entry,
    Flags,
    MatchFailure,
    MatchResult,
    MatchSuccess,
    RepoEntry,
    ScanIssue,
    StructureRuleList,
    StructureRuleMap,
)
from .paths import (
    join_path_normalized,
    map_dir_to_rel_dir,
    normalize_path,
    rel_dir_to_map_dir,
)
from .patterns import (
    expand_companion_requirements,
    extract_pattern_captures,
    substitute_pattern_captures,
)
from .scanning import (
    check_companion_files,
    expand_if_exists,
    expand_use_rule,
    get_matching_item_index,
    map_dir_to_entry_backlog,
    skip_entry,
    to_entry,
)

__all__ = [
    "BUILTIN_DIRECTORY_RULES",
    "IGNORE_RULE",
    "ConfigurationParseError",
    "DirectoryMap",
    "Entry",
    "Flags",
    "MatchFailure",
    "MatchResult",
    "MatchSuccess",
    "RepoEntry",
    "ScanIssue",
    "StructureRuleError",
    "StructureRuleList",
    "StructureRuleMap",
    "TemplateError",
    "check_companion_files",
    "expand_companion_requirements",
    "expand_if_exists",
    "expand_use_rule",
    "extract_pattern_captures",
    "get_matching_item_index",
    "join_path_normalized",
    "map_dir_to_entry_backlog",
    "map_dir_to_rel_dir",
    "normalize_path",
    "rel_dir_to_map_dir",
    "skip_entry",
    "substitute_pattern_captures",
    "to_entry",
]
