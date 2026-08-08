"""Unit tests for the exception hierarchy in errors.py."""

import pytest

from .errors import (
    ConfigurationParseError,
    RepoStructureError,
    StructureRuleError,
    TemplateError,
)

_ERROR_TYPES = [ConfigurationParseError, StructureRuleError, TemplateError]


@pytest.mark.parametrize("error_type", _ERROR_TYPES)
def test_errors_are_exceptions_carrying_a_message(error_type):
    """Test that every error type is raisable and keeps its message."""
    with pytest.raises(error_type, match="something went wrong"):
        raise error_type("something went wrong")


@pytest.mark.parametrize("error_type", _ERROR_TYPES)
def test_errors_share_a_catchable_base(error_type):
    """Test that catching the base class catches every error type."""
    with pytest.raises(RepoStructureError):
        raise error_type("something went wrong")
