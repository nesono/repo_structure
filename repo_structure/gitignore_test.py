"""Unit tests for gitignore.py, the root-relative .gitignore matcher."""

from pathlib import Path

import gitignore_parser
import pytest

from .gitignore import parse_gitignore


def _matcher(tmp_path: Path, contents: str):
    """Write a .gitignore below tmp_path and return the matcher for it."""
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text(contents, encoding="utf-8")
    return parse_gitignore(str(gitignore_path))


def test_matches_a_plain_name(tmp_path):
    """A bare name is ignored wherever it appears."""
    matches = _matcher(tmp_path, "debug.log\n")
    assert matches("debug.log")
    assert matches("sub/debug.log")
    assert not matches("debug.log.keep")
    assert not matches("other.log")


def test_matches_a_wildcard(tmp_path):
    """A wildcard does not cross directory separators."""
    matches = _matcher(tmp_path, "*.log\n")
    assert matches("debug.log")
    assert matches("sub/debug.log")
    assert not matches("debug.log/inner.txt")


def test_matches_an_anchored_pattern(tmp_path):
    """A pattern holding a slash is tied to the .gitignore's directory."""
    matches = _matcher(tmp_path, "build/output\n")
    assert matches("build/output")
    assert not matches("sub/build/output")


def test_matches_a_directory_only_pattern(tmp_path):
    """A trailing slash matches the directory and everything below it."""
    matches = _matcher(tmp_path, "build_output/\n")
    assert matches("build_output")
    assert matches("build_output/artifact.bin")
    assert matches("sub/build_output/artifact.bin")
    assert not matches("build_output.txt")


def test_matches_a_double_asterisk(tmp_path):
    """A leading '**/' matches at any depth."""
    matches = _matcher(tmp_path, "**/generated/*.py\n")
    assert matches("generated/thing.py")
    assert matches("deep/nested/generated/thing.py")
    assert not matches("generated/thing.txt")


def test_ignores_comments_and_blank_lines(tmp_path):
    """Comments and blank lines contribute no rules."""
    matches = _matcher(tmp_path, "\n# a comment\n\n*.log\n")
    assert matches("debug.log")
    assert not matches("# a comment")
    assert not matches("anything.txt")


def test_empty_file_matches_nothing(tmp_path):
    """A .gitignore holding no rules ignores nothing."""
    matches = _matcher(tmp_path, "")
    assert not matches("anything.txt")


def test_negation_reinstates_a_path(tmp_path):
    """A later negation wins over the rule that ignored the path."""
    matches = _matcher(tmp_path, "*.log\n!keep.log\n")
    assert matches("debug.log")
    assert not matches("keep.log")


def test_last_matching_rule_wins(tmp_path):
    """Ordering decides: a rule after a negation ignores the path again."""
    matches = _matcher(tmp_path, "*.log\n!keep.log\nkeep.log\n")
    assert matches("keep.log")


def test_negation_before_the_rule_does_not_win(tmp_path):
    """A negation listed first loses to the ignore rule that follows it."""
    matches = _matcher(tmp_path, "!keep.log\n*.log\n")
    assert matches("keep.log")


_PARITY_PATTERNS = """
*.log
!keep.log
build_output/
/anchored.txt
docs/*.md
**/generated/*.py
temp?
*.[oa]
# a comment

sub/deep/
"""

_PARITY_PATHS = (
    "debug.log",
    "keep.log",
    "sub/debug.log",
    "sub/keep.log",
    "build_output",
    "build_output/artifact.bin",
    "nested/build_output/artifact.bin",
    "anchored.txt",
    "sub/anchored.txt",
    "docs/guide.md",
    "docs/nested/guide.md",
    "generated/thing.py",
    "deep/nested/generated/thing.py",
    "temp1",
    "temps",
    "temp12",
    "object.o",
    "archive.a",
    "archive.b",
    "sub/deep",
    "sub/deep/file.txt",
    "README.md",
    "src/main.py",
)


@pytest.mark.parametrize("rel_path", _PARITY_PATHS)
def test_matches_gitignore_parser(tmp_path, rel_path):
    """Answer the same as the library this module replaced.

    The point of the module is to skip gitignore_parser's absolute-path
    handling, not to decide differently from it, so the two are compared
    directly: ours on the relative path, the library's on the absolute one.
    """
    ours = _matcher(tmp_path, _PARITY_PATTERNS)
    theirs = gitignore_parser.parse_gitignore(str(tmp_path / ".gitignore"))

    assert ours(rel_path) == theirs(str(tmp_path / rel_path))
