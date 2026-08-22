"""Matching a repository's .gitignore against root-relative paths.

``gitignore_parser`` matches absolute paths: every rule rebuilds a ``Path`` from
the path it is handed and calls ``relative_to`` to strip the repository root off
again. A scan already holds each entry's path relative to that root, so going
through an absolute path converts a string into the string it started from --
once per rule per entry. That dominated a full scan of a large repository, and
grew with the size of the ignore file, since every rule redid the conversion.

Translating a gitignore pattern into a regex is the subtle part of reading a
.gitignore, so that stays ``gitignore_parser``'s ``rule_from_pattern``. Only the
path handling around it is replaced here.
"""

import re
from typing import Callable

from gitignore_parser import rule_from_pattern

# What a compiled rule does to a path: report a match, or None.
_Search = Callable[[str], re.Match[str] | None]


def parse_gitignore(gitignore_path: str) -> Callable[[str], bool]:
    """Build a matcher for the .gitignore at ``gitignore_path``.

    The matcher answers True when a path is ignored. It takes paths relative to
    the directory holding the .gitignore, spelled with forward slashes and
    without a leading or trailing separator -- the form
    :func:`repo_structure.paths.join_path_normalized` produces.
    """
    rules = _compile_rules(gitignore_path)

    if not any(negation for _, negation in rules):
        # Without negation every rule points the same way, so the question is
        # only whether any of them matches.
        searches = [search for search, _ in rules]
        return lambda rel_path: any(search(rel_path) for search in searches)

    # With negation the *last* matching rule decides, so the rules are walked
    # backwards and the first hit answers.
    reversed_rules = list(reversed(rules))

    def match(rel_path: str) -> bool:
        for search, negation in reversed_rules:
            if search(rel_path):
                return not negation
        return False

    return match


def _compile_rules(gitignore_path: str) -> list[tuple[_Search, bool]]:
    """Compile every pattern in the file, keeping the order the file lists.

    Comments and blank lines yield no rule, which is how ``rule_from_pattern``
    reports them.
    """
    rules: list[tuple[_Search, bool]] = []
    with open(gitignore_path, encoding="utf-8") as gitignore_file:
        for line_number, line in enumerate(gitignore_file, start=1):
            rule = rule_from_pattern(
                line.rstrip("\n"), source=(gitignore_path, line_number)
            )
            if rule:
                rules.append((re.compile(rule.regex).search, rule.negation))
    return rules
