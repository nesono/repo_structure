"""Check the repository directory strucgure against your configuration."""

from .repo_structure_config import Configuration, ConfigurationParseError
from .repo_structure_enforcement import (
    fail_if_invalid_repo_structure,
    MissingMappingError,
    MissingRequiredEntriesError,
    UnspecifiedEntryError,
    EntryTypeMismatchError,
    Flags,
)

__all__ = [
    "Configuration",
    "ConfigurationParseError",
    "fail_if_invalid_repo_structure",
    "MissingMappingError",
    "MissingRequiredEntriesError",
    "UnspecifiedEntryError",
    "EntryTypeMismatchError",
    "Flags",
]

__version__ = "0.1.0"
