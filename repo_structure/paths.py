"""Path normalization and conversion helpers."""

import os
from pathlib import Path


def normalize_path(path: str) -> str:
    """Normalize path separators for cross-platform compatibility.

    Converts all path separators to forward slashes for consistent
    internal representation across Windows, macOS, and Linux.
    """
    return path.replace(os.sep, "/") if path else path


def join_path_normalized(*parts: str) -> str:
    """Join path parts and normalize separators for cross-platform compatibility.

    Uses pathlib.Path but ensures forward slashes in the result.
    """
    if not parts:
        return ""
    joined = Path(*parts)
    return normalize_path(str(joined))


def relative_to_root(path: str, repo_root: str) -> str | None:
    """Express `path` relative to `repo_root`, or None if it lies outside.

    Used to recognise the configuration file itself while scanning: it may be
    passed on the command line as any path, while scanning compares against
    paths relative to the repository root.
    """
    try:
        relative = Path(path).resolve().relative_to(Path(repo_root).resolve())
    except ValueError:
        return None
    return normalize_path(str(relative))


def rel_dir_to_map_dir(rel_dir: str):
    """Convert a relative directory path to a mapped directory path.

    This function ensures that a given relative directory path conforms to
    a specific format required for mapping. It enforces that the path starts
    and ends with a '/' character.
    """
    if not rel_dir or rel_dir == "/":
        return "/"

    if not rel_dir.startswith("/"):
        rel_dir = "/" + rel_dir
    if not rel_dir.endswith("/"):
        rel_dir = rel_dir + "/"

    return rel_dir


def map_dir_to_rel_dir(map_dir: str) -> str:
    """Convert a mapped directory path to a relative directory path.

    This function takes a mapped directory path and converts it back to
    a relative directory path by removing the leading and trailing '/'
    characters if they exist. If the input is the root directory or empty,
    it returns an empty string.
    """
    if not map_dir or map_dir == "/":
        return ""

    return map_dir[1:-1]
