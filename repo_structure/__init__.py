"""Check the repository directory strucgure against your configuration."""

from .repo_structure_config import Configuration
from .repo_structure_full_scan import (
    assert_full_repository_structure,
    MissingMappingError,
    MissingRequiredEntriesError,
    EntryTypeMismatchError,
)
from .repo_structure_diff_scan import assert_path
from .repo_structure_lib import Flags, UnspecifiedEntryError, ConfigurationParseError

__all__ = [
    "Configuration",
    "EntryTypeMismatchError",
    "MissingMappingError",
    "MissingRequiredEntriesError",
    "UnspecifiedEntryError",
    "ConfigurationParseError",
    "assert_full_repository_structure",
    "assert_path",
    "Flags",
]

__version__ = "0.1.0"
