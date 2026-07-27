"""Unit tests for the exception hierarchy in errors.py."""

import pytest

from repo_structure.errors import (
    ConfigurationParseError,
    StructureRuleError,
    TemplateError,
)


@pytest.mark.parametrize(
    "error_type",
    [ConfigurationParseError, StructureRuleError, TemplateError],
)
def test_errors_are_exceptions_carrying_a_message(error_type):
    """Test that every error type is raisable and keeps its message."""
    with pytest.raises(error_type, match="something went wrong"):
        raise error_type("something went wrong")
