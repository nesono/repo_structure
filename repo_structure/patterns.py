"""Capture extraction and template substitution for entry patterns."""

import re

from .errors import StructureRuleError
from .models import RepoEntry


def substitute_pattern_captures(pattern_template: str, captures: dict[str, str]) -> str:
    r"""Substitute captured group values into a pattern template.

    Captured values are passed through ``re.escape`` so any regex
    metacharacters in the captured filename are treated as literals.

    Args:
        pattern_template: Pattern string with {{name}} placeholders
        captures: Dictionary mapping capture group names to their values

    Returns:
        Pattern string with placeholders replaced by escaped captured values

    Example:
        >>> substitute_pattern_captures("{{base}}.h", {"base": "foo"})
        'foo\\.h'
    """
    result = pattern_template
    for name, value in captures.items():
        placeholder = f"{{{{{name}}}}}"
        result = result.replace(placeholder, re.escape(value))
    return result


def extract_pattern_captures(
    pattern: re.Pattern, filename: str
) -> dict[str, str] | None:
    r"""Extract named group captures from a pattern match.

    Args:
        pattern: Compiled regex pattern with named groups
        filename: Filename to match against the pattern

    Returns:
        Dictionary of captured group names to values, or None if no match

    Example:
        >>> pattern = re.compile(r'(?P<base>.*)\.cpp')
        >>> extract_pattern_captures(pattern, 'foo.cpp')
        {'base': 'foo'}
    """
    match = pattern.fullmatch(filename)
    if match:
        return match.groupdict()
    return None


def has_template_substitution(pattern: str) -> bool:
    """Check if a pattern contains template substitution placeholders like {{name}}."""
    return "{{" in pattern and "}}" in pattern


def expand_companion_requirements(
    companion_templates: list[RepoEntry], captures: dict[str, str]
) -> list[RepoEntry]:
    """Expand companion requirement templates with captured values.

    Args:
        companion_templates: List of RepoEntry templates with {{name}} placeholders
        captures: Dictionary of captured group values

    Returns:
        List of RepoEntry objects with patterns substituted

    Example:
        If companion has pattern "{{base}}.h" and captures = {"base": "foo"},
        returns RepoEntry with pattern "foo.h"
    """
    expanded = []
    for template in companion_templates:
        # Substitute captures in the pattern (values are re.escaped)
        expanded_pattern = substitute_pattern_captures(template.path.pattern, captures)

        # Compilation failures here indicate a malformed template (not a bad
        # capture value, since those are escaped). Surface them instead of
        # silently dropping required companion checks.
        try:
            compiled_pattern = re.compile(expanded_pattern)
        except re.error as exc:
            raise StructureRuleError(
                f"Companion pattern '{template.path.pattern}' expanded to "
                f"'{expanded_pattern}' which failed to compile: {exc}"
            ) from exc

        expanded_entry = RepoEntry(
            path=compiled_pattern,
            is_dir=template.is_dir,
            is_required=template.is_required,
            is_forbidden=template.is_forbidden,
            use_rule=template.use_rule,
            if_exists=template.if_exists,
            companion=[],
            count=0,
        )
        expanded.append(expanded_entry)

    return expanded
