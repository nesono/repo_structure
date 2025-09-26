"""Check the repository directory strucgure against your configuration."""

from .repo_structure_config import Configuration
from .repo_structure_full_scan import FullScanProcessor
from .repo_structure_diff_scan import DiffScanProcessor
from .repo_structure_lib import (
    Flags,
    ConfigurationParseError,
    ScanIssue,
    MatchResult,
)

__all__ = [
    "Configuration",
    "ConfigurationParseError",
    "FullScanProcessor",
    "DiffScanProcessor",
    "ScanIssue",
    "MatchResult",
    "Flags",
]

__version__ = "0.1.0"
