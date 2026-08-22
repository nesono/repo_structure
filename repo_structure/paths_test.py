"""Unit tests for paths.py path helpers."""

# pylint: disable=too-few-public-methods

from pathlib import Path
from unittest.mock import patch

from .paths import (
    join_path_normalized,
    map_dir_to_rel_dir,
    normalize_path,
    rel_dir_to_map_dir,
)


class TestNormalizePath:
    """Test the normalize_path function."""

    def test_normalize_path_forward_slashes(self):
        """Test that forward slashes are preserved."""
        assert normalize_path("path/to/file") == "path/to/file"

    @patch("repo_structure.paths.os.sep", "\\")
    def test_normalize_path_backslashes(self):
        """Test that backslashes are converted to forward slashes on Windows."""
        assert normalize_path("path\\to\\file") == "path/to/file"

    @patch("repo_structure.paths.os.sep", "\\")
    def test_normalize_path_mixed_separators(self):
        """Test that mixed separators are normalized on Windows."""
        assert normalize_path("path\\to/file\\name") == "path/to/file/name"

    def test_normalize_path_empty_string(self):
        """Test that empty string is handled correctly."""
        assert normalize_path("") == ""

    def test_normalize_path_root(self):
        """Test that root paths are handled correctly."""
        assert normalize_path("/") == "/"

    @patch("repo_structure.paths.os.sep", "\\")
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
        # This should behave like Path() / operator but normalized
        expected = normalize_path(str(Path("") / "file.txt"))
        assert result == expected

    def test_join_path_normalized_windows_style(self):
        """Test that result is normalized even if Path returns backslashes."""
        # This test ensures our function works correctly on Windows
        parts = ["path", "to", "file"]
        result = join_path_normalized(*parts)
        assert "/" in result or result == "path/to/file"
        assert "\\" not in result

    def test_join_path_normalized_trailing_empty_string(self):
        """Test that a trailing empty part adds no trailing separator."""
        assert join_path_normalized("dir", "") == "dir"

    def test_join_path_normalized_drops_dot_parts(self):
        """Test that a '.' part is dropped, as Path(...) used to drop it.

        config_merge joins ``str(Path(fs_path).parent)``, which is '.' for a
        configuration named without a directory, so keeping it would prefix
        every mounted configuration's path with './'.
        """
        assert join_path_normalized(".", "sub", "config.yaml") == "sub/config.yaml"

    def test_join_path_normalized_only_empty_parts(self):
        """Test that joining nothing meaningful yields an empty path."""
        assert join_path_normalized("", "") == ""
        assert join_path_normalized(".") == ""

    def test_join_path_normalized_part_with_trailing_separator(self):
        """Test that a part already ending in a separator is not doubled."""
        assert join_path_normalized("dir/", "file.txt") == "dir/file.txt"

    def test_join_path_normalized_filesystem_root(self):
        """Test that the filesystem root joins without doubling its separator."""
        assert join_path_normalized("/", "", "config.yaml") == "/config.yaml"


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
