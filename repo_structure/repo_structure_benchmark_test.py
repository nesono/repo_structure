"""Tests for repo_structure benchmark."""

import os
from typing import Final
import pytest

from .repo_structure_test_lib import with_random_repo_structure_in_tmpdir
from .repo_structure_full_scan import FullScanProcessor
from .repo_structure_config import Configuration


ALLOW_ALL_CONFIG: Final = """
structure_rules:
  allow_all:
    - description: 'Allow all files and directories'
    - allow: '.*'
    - allow: '.*/'
      use_rule: allow_all
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: allow_all
"""


@pytest.mark.skipif(
    os.environ.get("GITHUB_RUN_ID", "") != "", reason="Only run on local machine."
)
@with_random_repo_structure_in_tmpdir()
def test_benchmark_repo_structure_default(benchmark):
    """Test repo_structure benchmark."""
    config = Configuration(ALLOW_ALL_CONFIG, True)
    processor = FullScanProcessor(".", config)
    benchmark(processor.scan)
