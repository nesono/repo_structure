"""Unit tests for scanning.py entry skipping, matching and backlog building."""

# pylint: disable=too-few-public-methods

import re
from unittest.mock import Mock

from repo_structure.models import Entry, Flags, MatchSuccess, RepoEntry
from repo_structure.scanning import (
    _build_active_entry_backlog,
    expand_if_exists,
    expand_use_rule,
    get_matching_item_index,
    map_dir_to_entry_backlog,
    skip_entry,
    to_entry,
)

_SCANNING_LOGGER = "repo_structure.scanning"


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
    """Test the get_matching_item_index function."""

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
        assert result == MatchSuccess(index=0)

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
        assert result == MatchSuccess(index=0)

    def test_get_matching_item_index_verbose_output(self, caplog):
        """Test verbose output when finding a match."""
        backlog = [
            RepoEntry(
                path=re.compile(r"file\.txt"),
                is_dir=False,
                is_required=False,
                is_forbidden=False,
            )
        ]

        with caplog.at_level("DEBUG", logger=_SCANNING_LOGGER):
            get_matching_item_index(backlog, "file.txt", False, verbose=True)
        assert "Found match at index 0: 'file\\.txt'" in caplog.text


class TestHandleUseRule:
    """Test the expand_use_rule function."""

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

    def test_handle_use_rule_verbose_output(self, caplog):
        """Test verbose output when use_rule is found."""
        structure_rules = {"test_rule": []}
        flags = Flags(verbose=True)

        with caplog.at_level("DEBUG", logger=_SCANNING_LOGGER):
            expand_use_rule("test_rule", structure_rules, flags, "app")
        assert "use_rule found for rel path 'app'" in caplog.text


class TestHandleIfExists:
    """Test the expand_if_exists function."""

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

    def test_handle_if_exists_verbose_output(self, caplog):
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

        with caplog.at_level("DEBUG", logger=_SCANNING_LOGGER):
            expand_if_exists(backlog_entry, flags)
        assert "if_exists found for rel path 'test_pattern'" in caplog.text


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
    """Test the map_dir_to_entry_backlog function."""

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
