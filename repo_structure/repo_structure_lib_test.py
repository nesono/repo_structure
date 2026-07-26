"""Tests for the deprecated repo_structure_lib re-export shim.

The implementations are tested in errors_test.py, models_test.py,
paths_test.py, patterns_test.py and scanning_test.py. These tests only
guarantee that importing from the old module still yields the same objects.
"""

import pytest

from . import errors, models, paths, patterns, repo_structure_lib, scanning


@pytest.mark.parametrize("name", repo_structure_lib.__all__)
def test_shim_re_exports_the_original_object(name):
    """Test that every exported name resolves to the object in its new home."""
    shimmed = getattr(repo_structure_lib, name)
    sources = [
        module
        for module in (errors, models, paths, patterns, scanning)
        if hasattr(module, name)
    ]
    assert sources, f"{name} is not defined in any of the new modules"
    for module in sources:
        assert getattr(module, name) is shimmed


def test_shim_exports_every_public_name():
    """Test that __all__ stays in sync with the module's public attributes."""
    public = {name for name in vars(repo_structure_lib) if not name.startswith("_")}
    assert public == set(repo_structure_lib.__all__)
