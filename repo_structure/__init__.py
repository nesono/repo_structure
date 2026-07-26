"""Check the repository directory structure against your configuration."""

from .repo_structure_config import Configuration
from .repo_structure_full_scan import FullScanProcessor
from .repo_structure_diff_scan import DiffScanProcessor
from .errors import ConfigurationParseError
from .models import (
    Flags,
    ScanIssue,
    MatchResult,
    MatchSuccess,
    MatchFailure,
)

__all__ = [
    "Configuration",
    "ConfigurationParseError",
    "FullScanProcessor",
    "DiffScanProcessor",
    "ScanIssue",
    "MatchResult",
    "MatchSuccess",
    "MatchFailure",
    "Flags",
]

__version__ = "0.1.0"
