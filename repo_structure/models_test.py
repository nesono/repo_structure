"""Unit tests for the shared data types in models.py."""

# pylint: disable=too-few-public-methods

import re

from .models import (
    BUILTIN_DIRECTORY_RULES,
    IGNORE_RULE,
    BacklogEntry,
    Entry,
    Flags,
    MatchFailure,
    MatchSuccess,
    RepoEntry,
    ScanIssue,
    ScanResult,
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


class TestBacklogEntry:
    """Test the BacklogEntry dataclass."""

    @staticmethod
    def _entry() -> RepoEntry:
        return RepoEntry(
            path=re.compile(r".*\.py"),
            is_dir=False,
            is_required=True,
            is_forbidden=False,
        )

    def test_counting_is_per_backlog_entry(self):
        """Test that two backlog entries over one rule entry count separately."""
        shared = self._entry()
        first = BacklogEntry(entry=shared, is_required=shared.is_required)
        second = BacklogEntry(entry=shared, is_required=shared.is_required)

        first.count += 1

        assert first.count == 1
        assert second.count == 0

    def test_required_can_differ_from_the_rule_entry(self):
        """Test that a companion may join the backlog as optional."""
        required_entry = self._entry()
        candidate = BacklogEntry(entry=required_entry, is_required=False)

        assert required_entry.is_required is True
        assert candidate.is_required is False


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


class TestScanResult:
    """Test the ScanResult dataclass."""

    def test_empty_result_is_successful(self):
        """Test that a result without issues defaults to empty and successful."""
        result = ScanResult()
        assert not result.errors
        assert not result.warnings
        assert result.is_success

    def test_errors_fail_the_scan(self):
        """Test that any error makes the result unsuccessful."""
        issue = ScanIssue(severity="error", code="unspecified_entry", message="nope")
        assert not ScanResult(errors=[issue]).is_success

    def test_warnings_alone_do_not_fail_the_scan(self):
        """Test that warnings are reported without failing the scan."""
        warning = ScanIssue(
            severity="warning", code="unused_structure_rule", message="unused"
        )
        result = ScanResult(warnings=[warning])
        assert result.is_success
        assert result.warnings == [warning]

    def test_default_lists_are_not_shared(self):
        """Test that each instance gets its own list instances."""
        first = ScanResult()
        second = ScanResult()
        first.errors.append(
            ScanIssue(severity="error", code="unspecified_entry", message="nope")
        )
        assert not second.errors


class TestMatchResult:
    """Test the MatchResult variants."""

    def test_match_success_holds_index(self):
        """Test that MatchSuccess exposes the matched index."""
        assert MatchSuccess(index=3).index == 3

    def test_match_failure_holds_reason_and_entry(self):
        """Test that MatchFailure exposes the failure reason and entry."""
        failure = MatchFailure(
            code="unspecified_entry", entry_path="widget.cpp", is_dir=False
        )
        assert failure.code == "unspecified_entry"
        assert failure.entry_path == "widget.cpp"
        assert not failure.is_dir

    def test_variants_are_distinguishable(self):
        """Test that the two variants never compare equal."""
        failure = MatchFailure(
            code="unspecified_entry", entry_path="widget.cpp", is_dir=False
        )
        assert MatchSuccess(index=0) != failure


class TestBuiltinDirectoryRules:
    """Test the builtin directory rule constants."""

    def test_ignore_is_a_builtin_rule(self):
        """Test that the ignore rule is part of the builtins."""
        assert IGNORE_RULE == "ignore"
        assert IGNORE_RULE in BUILTIN_DIRECTORY_RULES
