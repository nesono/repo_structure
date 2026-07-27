"""Unit tests for patterns.py capture and substitution helpers."""

# pylint: disable=too-few-public-methods

import re
from dataclasses import dataclass
from typing import cast

import pytest

from repo_structure.errors import StructureRuleError
from repo_structure.models import RepoEntry
from repo_structure.patterns import (
    expand_companion_requirements,
    extract_pattern_captures,
    has_template_substitution,
    substitute_pattern_captures,
)


@dataclass
class _RawPattern:
    """Stand-in exposing only the ``pattern`` source string of a compiled regex."""

    pattern: str


class TestPatternCaptureAndSubstitution:
    """Test pattern capture and substitution functions."""

    def test_substitute_pattern_captures_single_capture(self):
        """Test substituting a single captured value."""
        pattern_template = "{{base}}.h"
        captures = {"base": "foo"}
        result = substitute_pattern_captures(pattern_template, captures)
        assert result == "foo.h"

    def test_substitute_pattern_captures_multiple_captures(self):
        """Test substituting multiple captured values."""
        pattern_template = "{{dir}}/{{base}}.{{ext}}"
        captures = {"dir": "src", "base": "main", "ext": "cpp"}
        result = substitute_pattern_captures(pattern_template, captures)
        assert result == "src/main.cpp"

    def test_substitute_pattern_captures_no_captures(self):
        """Test pattern with no placeholders."""
        pattern_template = "fixed.txt"
        captures = {"base": "foo"}
        result = substitute_pattern_captures(pattern_template, captures)
        assert result == "fixed.txt"

    def test_extract_pattern_captures_simple(self):
        """Test extracting captures from a simple pattern."""
        pattern = re.compile(r"(?P<base>.*)\.cpp")
        captures = extract_pattern_captures(pattern, "foo.cpp")
        assert captures == {"base": "foo"}

    def test_extract_pattern_captures_multiple_groups(self):
        """Test extracting multiple capture groups."""
        pattern = re.compile(r"(?P<dir>.*)/(?P<base>.*)\.(?P<ext>.*)")
        captures = extract_pattern_captures(pattern, "src/main.cpp")
        assert captures == {"dir": "src", "base": "main", "ext": "cpp"}

    def test_extract_pattern_captures_no_match(self):
        """Test extraction when pattern doesn't match."""
        pattern = re.compile(r"(?P<base>.*)\.cpp")
        captures = extract_pattern_captures(pattern, "foo.h")
        assert captures is None

    def test_extract_pattern_captures_partial_match(self):
        """Test that partial matches don't count (uses fullmatch)."""
        pattern = re.compile(r"(?P<base>.*)\.cpp")
        captures = extract_pattern_captures(pattern, "foo.cpp.bak")
        assert captures is None

    def test_expand_companion_requirements_simple(self):
        """Test expanding companion requirements with captures."""
        companion_template = RepoEntry(
            path=re.compile("{{base}}.h"),
            is_dir=False,
            is_required=True,
            is_forbidden=False,
        )
        captures = {"base": "foo"}
        expanded = expand_companion_requirements([companion_template], captures)

        assert len(expanded) == 1
        assert expanded[0].path.pattern == "foo.h"
        assert expanded[0].is_required

    def test_expand_companion_requirements_multiple(self):
        """Test expanding multiple companion requirements."""
        companions = [
            RepoEntry(
                path=re.compile("{{base}}.h"),
                is_dir=False,
                is_required=True,
                is_forbidden=False,
            ),
            RepoEntry(
                path=re.compile("{{base}}_test.cpp"),
                is_dir=False,
                is_required=False,
                is_forbidden=False,
            ),
        ]
        captures = {"base": "widget"}
        expanded = expand_companion_requirements(companions, captures)

        assert len(expanded) == 2
        assert expanded[0].path.pattern == "widget.h"
        assert expanded[0].is_required
        assert expanded[1].path.pattern == "widget_test.cpp"
        assert not expanded[1].is_required

    def test_expand_companion_requirements_escapes_capture_metacharacters(self):
        """Capture values containing regex metacharacters are escaped, not interpreted."""
        companion_template = RepoEntry(
            path=re.compile("{{base}}\\.h"),
            is_dir=False,
            is_required=True,
            is_forbidden=False,
        )
        # A literal "foo(bar" capture would have previously yielded an invalid
        # pattern; re.escape now keeps it as a literal match string.
        captures = {"base": "foo(bar"}
        expanded = expand_companion_requirements([companion_template], captures)

        assert len(expanded) == 1
        # The resulting compiled pattern matches the literal "foo(bar.h"
        assert expanded[0].path.fullmatch("foo(bar.h") is not None

    def test_expand_companion_requirements_malformed_template(self):
        """A template whose expansion does not compile surfaces a StructureRuleError."""
        # Captures are re.escape'd, so only a malformed template can produce an
        # uncompilable expansion. Patch the raw pattern source to simulate one.
        companion_template = RepoEntry(
            path=cast(re.Pattern, _RawPattern("{{base}}(")),
            is_dir=False,
            is_required=True,
            is_forbidden=False,
        )

        with pytest.raises(StructureRuleError, match="failed to compile"):
            expand_companion_requirements([companion_template], {"base": "foo"})


class TestHasTemplateSubstitution:
    """Test the has_template_substitution function."""

    def test_pattern_with_placeholder(self):
        """Test that a placeholder is detected."""
        assert has_template_substitution("{{base}}_test.py") is True

    def test_pattern_without_placeholder(self):
        """Test that a plain pattern is not flagged."""
        assert has_template_substitution(r".*\.py") is False

    def test_pattern_with_unbalanced_braces(self):
        """Test that opening braces alone are not flagged."""
        assert has_template_substitution("{{base") is False
