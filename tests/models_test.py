"""Unit tests for the shared data types in models.py."""

# pylint: disable=too-few-public-methods

import re

from repo_structure.models import (
    BUILTIN_DIRECTORY_RULES,
    IGNORE_RULE,
    Entry,
    Flags,
    MatchFailure,
    MatchSuccess,
    RepoEntry,
    ScanIssue,
)


class TestRepoEntry:
    """Test the RepoEntry dataclass."""

    def test_optional_fields_default_to_empty(self):
        """Test that optional fields have empty defaults."""
        entry = RepoEntry(
            path=re.compile(r".*\.py"),
            is_dir=False,
            is_required=True,
            is_forbidden=False,
        )
        assert entry.use_rule == ""
        assert not entry.if_exists
        assert not entry.companion
        assert entry.count == 0

    def test_default_lists_are_not_shared(self):
        """Test that each instance gets its own list instances."""
        first = RepoEntry(
            path=re.compile(r"a"), is_dir=False, is_required=False, is_forbidden=False
        )
        second = RepoEntry(
            path=re.compile(r"b"), is_dir=False, is_required=False, is_forbidden=False
        )
        first.if_exists.append(second)
        assert not second.if_exists


class TestEntry:
    """Test the Entry dataclass."""

    def test_entry_fields(self):
        """Test that all fields are stored as given."""
        entry = Entry(path="file.txt", rel_dir="app", is_dir=False, is_symlink=True)
        assert entry.path == "file.txt"
        assert entry.rel_dir == "app"
        assert entry.is_dir is False
        assert entry.is_symlink is True


class TestFlags:
    """Test the Flags dataclass."""

    def test_flags_defaults(self):
        """Test the default flag values."""
        flags = Flags()
        assert flags.follow_symlinks is False
        assert flags.include_hidden is True
        assert flags.verbose is False


class TestScanIssue:
    """Test the ScanIssue dataclass."""

    def test_path_is_optional(self):
        """Test that path defaults to None."""
        issue = ScanIssue(severity="warning", code="some_code", message="message")
        assert issue.path is None

    def test_issues_compare_by_value(self):
        """Test that issues with the same content compare equal."""
        issue = ScanIssue(
            severity="error", code="forbidden_entry", message="nope", path="a.txt"
        )
        same = ScanIssue(
            severity="error", code="forbidden_entry", message="nope", path="a.txt"
        )
        assert issue == same


class TestMatchResult:
    """Test the MatchResult variants."""

    def test_match_success_holds_index(self):
        """Test that MatchSuccess exposes the matched index."""
        assert MatchSuccess(index=3).index == 3

    def test_match_failure_holds_issue(self):
        """Test that MatchFailure exposes the issue."""
        issue = ScanIssue(severity="error", code="unspecified_entry", message="nope")
        assert MatchFailure(issue=issue).issue is issue

    def test_variants_are_distinguishable(self):
        """Test that the two variants never compare equal."""
        issue = ScanIssue(severity="error", code="unspecified_entry", message="nope")
        assert MatchSuccess(index=0) != MatchFailure(issue=issue)


class TestBuiltinDirectoryRules:
    """Test the builtin directory rule constants."""

    def test_ignore_is_a_builtin_rule(self):
        """Test that the ignore rule is part of the builtins."""
        assert IGNORE_RULE == "ignore"
        assert IGNORE_RULE in BUILTIN_DIRECTORY_RULES
