"""Check the repository directory structure against your configuration."""

from .config import Configuration
from .full_scan import FullScanProcessor
from .diff_scan import DiffScanProcessor
from .errors import ConfigurationParseError
from .models import (
    Flags,
    ScanIssue,
    ScanResult,
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
    "ScanResult",
    "MatchResult",
    "MatchSuccess",
    "MatchFailure",
    "Flags",
]

__version__ = "0.1.0"
