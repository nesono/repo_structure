"""Check the repository directory strucgure against your configuration."""

from .repo_structure_config import Configuration, ConfigurationParseError
from .repo_structure_enforcement import (
    assert_full_repository_structure,
    assert_path,
    MissingMappingError,
    MissingRequiredEntriesError,
    UnspecifiedEntryError,
    EntryTypeMismatchError,
    Flags,
)

__all__ = [
    "Configuration",
    "ConfigurationParseError",
    "EntryTypeMismatchError",
    "Flags",
    "MissingMappingError",
    "MissingRequiredEntriesError",
    "UnspecifiedEntryError",
    "assert_full_repository_structure",
    "assert_path",
]

__version__ = "0.1.0"
