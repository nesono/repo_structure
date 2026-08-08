"""Tests for repo_structure benchmark."""

import os
from typing import Final
import pytest

from .test_lib import create_random_repo_structure, create_repo_structure
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

COMPANION_CONFIG: Final = r"""
structure_rules:
  sources_with_tests:
    - description: 'Every module needs a test beside it'
    - allow: '(?P<base>.*)_test\.py'
    - allow: '(?P<base>.*)\.py'
      companion:
        - require: '{{base}}_test\.py'
directory_map:
  /:
    - description: 'Root directory'
    - use_rule: sources_with_tests
"""

_COMPANION_MODULE_COUNT: Final = 150


@pytest.mark.skipif(
    os.environ.get("GITHUB_RUN_ID", "") != "", reason="Only run on local machine."
)
def test_benchmark_repo_structure_default(benchmark, tmp_path):
    """Test repo_structure benchmark."""
    repo = create_random_repo_structure(tmp_path)
    config = Configuration.from_yaml_string(ALLOW_ALL_CONFIG)
    processor = FullScanProcessor(repo, config)
    benchmark(processor.scan)


@pytest.mark.skipif(
    os.environ.get("GITHUB_RUN_ID", "") != "", reason="Only run on local machine."
)
def test_benchmark_companion_heavy_directory(benchmark, tmp_path):
    """Benchmark a directory where every file triggers a companion lookup.

    Each companion is searched for below the matched file's directory, so this
    is the case that used to walk the same subtree once per module.
    """
    specification = "\n".join(
        f"module_{i}.py\nmodule_{i}_test.py" for i in range(_COMPANION_MODULE_COUNT)
    )
    repo = create_repo_structure(tmp_path, specification)
    config = Configuration.from_yaml_string(COMPANION_CONFIG)
    processor = FullScanProcessor(repo, config)

    result = benchmark(processor.scan)
    assert result.is_success
