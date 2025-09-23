"""Check the repository directory strucgure against your configuration."""

from .repo_structure_config import Configuration
from .repo_structure_full_scan import (
    scan_full_repository,
)
from .repo_structure_diff_scan import check_path
from .repo_structure_lib import Flags, UnspecifiedEntryError, ConfigurationParseError

__all__ = [
    "Configuration",
    "UnspecifiedEntryError",
    "ConfigurationParseError",
    "scan_full_repository",
    "check_path",
    "Flags",
]

__version__ = "0.1.0"
