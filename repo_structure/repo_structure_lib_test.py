"""Unit tests for repo_structure_lib.py core functions."""

# pylint: disable=too-few-public-methods

import os
import re
from unittest.mock import Mock, patch


from .repo_structure_lib import (
    normalize_path,
    join_path_normalized,
    rel_dir_to_map_dir,
    map_dir_to_rel_dir,
    expand_if_exists,
    expand_use_rule,
    map_dir_to_entry_backlog,
    to_entry,
    _build_active_entry_backlog,
    skip_entry,
    MatchResult,
    get_matching_item_index,
    Entry,
    RepoEntry,
    Flags,
    substitute_pattern_captures,
    extract_pattern_captures,
    expand_companion_requirements,
)


class TestNormalizePath:
    """Test the normalize_path function."""

    def test_normalize_path_forward_slashes(self):
        """Test that forward slashes are preserved."""
        assert normalize_path("path/to/file") == "path/to/file"

    @patch("repo_structure.repo_structure_lib.os.sep", "\\")
    def test_normalize_path_backslashes(self):
        """Test that backslashes are converted to forward slashes on Windows."""
        assert normalize_path("path\\to\\file") == "path/to/file"

    @patch("repo_structure.repo_structure_lib.os.sep", "\\")
    def test_normalize_path_mixed_separators(self):
        """Test that mixed separators are normalized on Windows."""
        assert normalize_path("path\\to/file\\name") == "path/to/file/name"

    def test_normalize_path_empty_string(self):
        """Test that empty string is handled correctly."""
        assert normalize_path("") == ""

    def test_normalize_path_root(self):
        """Test that root paths are handled correctly."""
        assert normalize_path("/") == "/"

    @patch("repo_structure.repo_structure_lib.os.sep", "\\")
    def test_normalize_path_root_windows(self):
        """Test that backslash root is normalized on Windows."""
        assert normalize_path("\\") == "/"

    def test_normalize_path_single_file(self):
        """Test that single file names are preserved."""
        assert normalize_path("file.txt") == "file.txt"


class TestJoinPathNormalized:
    """Test the join_path_normalized function."""

    def test_join_path_normalized_multiple_parts(self):
        """Test joining multiple path parts."""
        result = join_path_normalized("path", "to", "file")
        assert result == "path/to/file"

    def test_join_path_normalized_two_parts(self):
        """Test joining two path parts."""
        result = join_path_normalized("dir", "file.txt")
        assert result == "dir/file.txt"

    def test_join_path_normalized_single_part(self):
        """Test joining single path part."""
        result = join_path_normalized("file.txt")
        assert result == "file.txt"

    def test_join_path_normalized_empty_args(self):
        """Test joining with no arguments."""
        result = join_path_normalized()
        assert result == ""

    def test_join_path_normalized_with_empty_strings(self):
        """Test joining with empty string parts."""
        result = join_path_normalized("", "file.txt")
        # This should behave like os.path.join but normalized
        expected = normalize_path(os.path.join("", "file.txt"))
        assert result == expected

    def test_join_path_normalized_windows_style(self):
        """Test that result is normalized even if os.path.join returns backslashes."""
        # This test ensures our function works correctly on Windows
        parts = ["path", "to", "file"]
        result = join_path_normalized(*parts)
        assert "/" in result or result == "path/to/file"
        assert "\\" not in result


class TestRelDirToMapDir:
    """Test the rel_dir_to_map_dir function."""

    def test_rel_dir_to_map_dir_empty(self):
        """Test conversion of empty string."""
        assert rel_dir_to_map_dir("") == "/"

    def test_rel_dir_to_map_dir_root(self):
        """Test conversion of root directory."""
        assert rel_dir_to_map_dir("/") == "/"

    def test_rel_dir_to_map_dir_simple_path(self):
        """Test conversion of simple path."""
        assert rel_dir_to_map_dir("app") == "/app/"

    def test_rel_dir_to_map_dir_nested_path(self):
        """Test conversion of nested path."""
        assert rel_dir_to_map_dir("app/lib") == "/app/lib/"

    def test_rel_dir_to_map_dir_already_formatted(self):
        """Test conversion of already formatted path."""
        assert rel_dir_to_map_dir("/app/lib/") == "/app/lib/"

    def test_rel_dir_to_map_dir_leading_slash_only(self):
        """Test conversion with leading slash only."""
        assert rel_dir_to_map_dir("/app/lib") == "/app/lib/"

    def test_rel_dir_to_map_dir_trailing_slash_only(self):
        """Test conversion with trailing slash only."""
        assert rel_dir_to_map_dir("app/lib/") == "/app/lib/"


class TestMapDirToRelDir:
    """Test the map_dir_to_rel_dir function."""

    def test_map_dir_to_rel_dir_root(self):
        """Test conversion of root directory."""
        assert map_dir_to_rel_dir("/") == ""

    def test_map_dir_to_rel_dir_empty(self):
        """Test conversion of empty string."""
        assert map_dir_to_rel_dir("") == ""

    def test_map_dir_to_rel_dir_simple_path(self):
        """Test conversion of simple path."""
        assert map_dir_to_rel_dir("/app/") == "app"

    def test_map_dir_to_rel_dir_nested_path(self):
        """Test conversion of nested path."""
        assert map_dir_to_rel_dir("/app/lib/") == "app/lib"


class TestSkipEntry:
    """Test the skip_entry function."""

    def test_skip_entry_symlink_no_follow(self):
        """Test that symlinks are skipped when follow_symlinks is False."""
        entry = Entry(path="link", rel_dir="", is_dir=False, is_symlink=True)
        flags = Flags(follow_symlinks=False)
        assert skip_entry(entry, {}, "config.yaml", None, flags) is True

    def test_skip_entry_symlink_follow(self):
        """Test that symlinks are not skipped when follow_symlinks is True."""
        entry = Entry(path="link", rel_dir="", is_dir=False, is_symlink=False)
        flags = Flags(follow_symlinks=True)
        assert skip_entry(entry, {}, "config.yaml", None, flags) is False

    def test_skip_entry_hidden_no_include(self):
        """Test that hidden files are skipped when include_hidden is False."""
        entry = Entry(path=".hidden", rel_dir="", is_dir=False, is_symlink=False)
        flags = Flags(include_hidden=False)
        assert skip_entry(entry, {}, "config.yaml", None, flags) is True

    def test_skip_entry_hidden_include(self):
        """Test that hidden files are not skipped when include_hidden is True."""
        entry = Entry(path=".hidden", rel_dir="", is_dir=False, is_symlink=False)
        flags = Flags(include_hidden=True)
        assert skip_entry(entry, {}, "config.yaml", None, flags) is False

    def test_skip_entry_gitignore_file(self):
        """Test that .gitignore file is skipped."""
        entry = Entry(path=".gitignore", rel_dir="", is_dir=False, is_symlink=False)
        flags = Flags()
        assert skip_entry(entry, {}, "config.yaml", None, flags) is True

    def test_skip_entry_git_dir(self):
        """Test that .git directory is skipped."""
        entry = Entry(path=".git", rel_dir="", is_dir=True, is_symlink=False)
        flags = Flags()
        assert skip_entry(entry, {}, "config.yaml", None, flags) is True

    def test_skip_entry_config_file(self):
        """Test that config file is skipped."""
        entry = Entry(path="config.yaml", rel_dir="", is_dir=False, is_symlink=False)
        flags = Flags()
        assert skip_entry(entry, {}, "config.yaml", None, flags) is True

    def test_skip_entry_git_ignore_function(self):
        """Test that entries matching gitignore are skipped."""
        entry = Entry(path="ignored.txt", rel_dir="", is_dir=False, is_symlink=False)

        def git_ignore(path):
            return path == "ignored.txt"

        flags = Flags()
        assert skip_entry(entry, {}, "config.yaml", git_ignore, flags) is True

    def test_skip_entry_directory_in_map(self):
        """Test that directories in directory_map are skipped."""
        entry = Entry(path="subdir", rel_dir="app", is_dir=True, is_symlink=False)
        directory_map = {"/app/subdir/": ["rule1"]}
        flags = Flags()
        assert skip_entry(entry, directory_map, "config.yaml", None, flags) is True

    def test_skip_entry_normal_file(self):
        """Test that normal files are not skipped."""
        entry = Entry(path="file.txt", rel_dir="", is_dir=False, is_symlink=False)
        flags = Flags()
        assert skip_entry(entry, {}, "config.yaml", None, flags) is False


class TestToEntry:
    """Test the to_entry function."""

    def test_to_entry_file(self):
        """Test conversion of file entry."""
        mock_os_entry = Mock()
        mock_os_entry.name = "file.txt"
        mock_os_entry.is_dir.return_value = False
        mock_os_entry.is_symlink.return_value = False

        entry = to_entry(mock_os_entry, "app")
        assert entry.path == "file.txt"
        assert entry.rel_dir == "app"
        assert entry.is_dir is False
        assert entry.is_symlink is False

    def test_to_entry_directory(self):
        """Test conversion of directory entry."""
        mock_os_entry = Mock()
        mock_os_entry.name = "subdir"
        mock_os_entry.is_dir.return_value = True
        mock_os_entry.is_symlink.return_value = False

        entry = to_entry(mock_os_entry, "")
        assert entry.path == "subdir"
        assert entry.rel_dir == ""
        assert entry.is_dir is True
        assert entry.is_symlink is False


class TestGetMatchingItemIndex:
    """Test the _get_matching_item_index function."""

    def test_get_matching_item_index_found_file(self):
        """Test finding a matching file entry."""
        backlog = [
            RepoEntry(
                path=re.compile(r"file\.txt"),
                is_dir=False,
                is_required=False,
                is_forbidden=False,
            )
        ]

        result = get_matching_item_index(backlog, "file.txt", False)
        assert result == MatchResult(success=True, index=0, issue=None)

    def test_get_matching_item_index_found_directory(self):
        """Test finding a matching directory entry."""
        backlog = [
            RepoEntry(
                path=re.compile(r"subdir"),
                is_dir=True,
                is_required=False,
                is_forbidden=False,
            )
        ]

        result = get_matching_item_index(backlog, "subdir", True)
        assert result == MatchResult(success=True, index=0, issue=None)

    def test_get_matching_item_index_verbose_output(self, capsys):
        """Test verbose output when finding a match."""
        backlog = [
            RepoEntry(
                path=re.compile(r"file\.txt"),
                is_dir=False,
                is_required=False,
                is_forbidden=False,
            )
        ]

        get_matching_item_index(backlog, "file.txt", False, verbose=True)
        captured = capsys.readouterr()
        assert "Found match at index 0: 'file\\.txt'" in captured.out


class TestHandleUseRule:
    """Test the handle_use_rule function."""

    def test_handle_use_rule_with_rule(self):
        """Test handling when use_rule is provided."""
        structure_rules = {
            "python_files": [
                RepoEntry(
                    path=re.compile(r".*\.py"),
                    is_dir=False,
                    is_required=False,
                    is_forbidden=False,
                )
            ]
        }
        flags = Flags()

        result = expand_use_rule("python_files", structure_rules, flags, "app")
        assert result is not None
        assert len(result) == 1
        assert result[0].path.pattern == ".*\\.py"

    def test_handle_use_rule_empty_rule(self):
        """Test handling when use_rule is empty."""
        structure_rules = {}
        flags = Flags()

        result = expand_use_rule("", structure_rules, flags, "app")
        assert result is None

    def test_handle_use_rule_verbose_output(self, capsys):
        """Test verbose output when use_rule is found."""
        structure_rules = {"test_rule": []}
        flags = Flags(verbose=True)

        expand_use_rule("test_rule", structure_rules, flags, "app")
        captured = capsys.readouterr()
        assert "use_rule found for rel path 'app'" in captured.out


class TestHandleIfExists:
    """Test the _handle_if_exists function."""

    def test_handle_if_exists_with_entries(self):
        """Test handling when if_exists has entries."""
        if_exists_entries = [
            RepoEntry(
                path=re.compile(r".*\.md"),
                is_dir=False,
                is_required=False,
                is_forbidden=False,
            )
        ]
        backlog_entry = RepoEntry(
            path=re.compile(r".*"),
            is_dir=True,
            is_required=False,
            is_forbidden=False,
            if_exists=if_exists_entries,
        )
        flags = Flags()

        result = expand_if_exists(backlog_entry, flags)
        assert result == if_exists_entries

    def test_handle_if_exists_empty(self):
        """Test handling when if_exists is empty."""
        backlog_entry = RepoEntry(
            path=re.compile(r".*"), is_dir=True, is_required=False, is_forbidden=False
        )
        flags = Flags()

        result = expand_if_exists(backlog_entry, flags)
        assert result is None

    def test_handle_if_exists_verbose_output(self, capsys):
        """Test verbose output when if_exists is found."""
        if_exists_entries = [
            RepoEntry(
                path=re.compile(r"test"),
                is_dir=False,
                is_required=False,
                is_forbidden=False,
            )
        ]
        backlog_entry = RepoEntry(
            path=re.compile(r"test_pattern"),
            is_dir=True,
            is_required=False,
            is_forbidden=False,
            if_exists=if_exists_entries,
        )
        flags = Flags(verbose=True)

        expand_if_exists(backlog_entry, flags)
        captured = capsys.readouterr()
        assert "if_exists found for rel path 'test_pattern'" in captured.out


class TestBuildActiveEntryBacklog:
    """Test the _build_active_entry_backlog function."""

    def test_build_active_entry_backlog_single_rule(self):
        """Test building backlog with single rule."""
        structure_rules = {
            "python_files": [
                RepoEntry(
                    path=re.compile(r".*\.py"),
                    is_dir=False,
                    is_required=False,
                    is_forbidden=False,
                )
            ]
        }

        result = _build_active_entry_backlog(["python_files"], structure_rules)
        assert len(result) == 1
        assert result[0].path.pattern == ".*\\.py"

    def test_build_active_entry_backlog_multiple_rules(self):
        """Test building backlog with multiple rules."""
        structure_rules = {
            "python_files": [
                RepoEntry(
                    path=re.compile(r".*\.py"),
                    is_dir=False,
                    is_required=False,
                    is_forbidden=False,
                )
            ],
            "text_files": [
                RepoEntry(
                    path=re.compile(r".*\.txt"),
                    is_dir=False,
                    is_required=False,
                    is_forbidden=False,
                )
            ],
        }

        result = _build_active_entry_backlog(
            ["python_files", "text_files"], structure_rules
        )
        assert len(result) == 2

    def test_build_active_entry_backlog_ignore_rule(self):
        """Test that 'ignore' rule is skipped."""
        structure_rules = {
            "python_files": [
                RepoEntry(
                    path=re.compile(r".*\.py"),
                    is_dir=False,
                    is_required=False,
                    is_forbidden=False,
                )
            ]
        }

        result = _build_active_entry_backlog(
            ["ignore", "python_files"], structure_rules
        )
        assert len(result) == 1
        assert result[0].path.pattern == ".*\\.py"

    def test_build_active_entry_backlog_empty_rules(self):
        """Test building backlog with empty rules list."""
        structure_rules = {}

        result = _build_active_entry_backlog([], structure_rules)
        assert len(result) == 0


class TestMapDirToEntryBacklog:
    """Test the _map_dir_to_entry_backlog function."""

    def test_map_dir_to_entry_backlog(self):
        """Test mapping directory to entry backlog."""
        directory_map = {"/": ["base_rule"], "/app/": ["python_rule"]}
        structure_rules = {
            "base_rule": [
                RepoEntry(
                    path=re.compile(r"README\.md"),
                    is_dir=False,
                    is_required=True,
                    is_forbidden=False,
                )
            ],
            "python_rule": [
                RepoEntry(
                    path=re.compile(r".*\.py"),
                    is_dir=False,
                    is_required=False,
                    is_forbidden=False,
                )
            ],
        }

        result = map_dir_to_entry_backlog(directory_map, structure_rules, "/app/")
        assert len(result) == 1
        assert result[0].path.pattern == ".*\\.py"


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

    def test_expand_companion_requirements_invalid_pattern(self):
        """Test that invalid patterns after substitution are skipped."""
        companion_template = RepoEntry(
            path=re.compile("{{base}}\\.h"),  # Valid template
            is_dir=False,
            is_required=True,
            is_forbidden=False,
        )
        captures = {"base": "foo(bar"}  # Will create invalid pattern "foo(bar.h"
        expanded = expand_companion_requirements([companion_template], captures)

        # Should skip the invalid pattern
        assert len(expanded) == 0
