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
from .__main__ import main

__all__ = [
    "Configuration",
    "ConfigurationParseError",
    "EntryTypeMismatchError",
    "Flags",
    "MissingMappingError",
    "MissingRequiredEntriesError",
    "UnspecifiedEntryError",
    "fail_if_invalid_repo_structure",
    "main",
]

__version__ = "0.1.0"
