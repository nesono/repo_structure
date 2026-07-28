"""Tests for repo_structure benchmark."""

import os
from typing import Final
import pytest

from .test_lib import create_random_repo_structure
from .full_scan import FullScanProcessor
from .config import Configuration


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
def test_benchmark_repo_structure_default(benchmark, tmp_path):
    """Test repo_structure benchmark."""
    repo = create_random_repo_structure(tmp_path)
    config = Configuration(ALLOW_ALL_CONFIG, True)
    processor = FullScanProcessor(repo, config)
    benchmark(processor.scan)
