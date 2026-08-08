"""Check the repository directory structure against your configuration."""

from .config import Configuration
from .full_scan import FullScanProcessor
from .diff_scan import DiffScanProcessor
from .errors import ConfigurationParseError, RepoStructureError
from .models import (
    Flags,
    ScanIssue,
    ScanResult,
    MatchResult,
    MatchSuccess,
    MatchFailure,
)

try:
    from ._version import version as __version__
except ModuleNotFoundError:  # pragma: no cover
    # _version.py is generated at build time by hatch-vcs.
    __version__ = "version unknown"

__all__ = [
    "Configuration",
    "ConfigurationParseError",
    "RepoStructureError",
    "FullScanProcessor",
    "DiffScanProcessor",
    "ScanIssue",
    "ScanResult",
    "MatchResult",
    "MatchSuccess",
    "MatchFailure",
    "Flags",
    "__version__",
]
