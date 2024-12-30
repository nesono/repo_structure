

from .repo_structure_test_lib import with_random_repo_structure_in_tmpdir
from .repo_structure_full_scan import assert_full_repository_structure
from .repo_structure_config import Configuration

from typing import Final


ALLOW_ALL_CONFIG: Final = """
structure_rules:
  allow_all:
    - allow: '.*'
    - allow: '.*/'
      use_rule: allow_all
directory_map:
  /:
    - use_rule: allow_all
"""

@with_random_repo_structure_in_tmpdir()
def test_benchmark_repo_structure_default(benchmark):
    """Test repo_structure benchmark."""
    config = Configuration(ALLOW_ALL_CONFIG, True)
    benchmark(assert_full_repository_structure, ".", config)
