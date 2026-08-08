"""Library functions for repo structure testing.

The helpers here build repository trees below a caller-supplied directory —
typically pytest's ``tmp_path`` fixture — and return that directory. Nothing
changes the process CWD, so tests must pass the returned path into the API
under test.
"""

import os
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
import random
import string
from typing import Callable, Sequence


def create_repo_structure(base_path: Path, specification: str) -> str:
    """Create a directory structure below base_path based on a specification.

    A specification file can contain the following entries:
    | Entry                      | Meaning                                                         |
    | # <string>                 | comment string (ignored in output)                              |
    | <filename>:<content>       | File with content <content> (single line only)                  |
    | <dirname>/                 | Directory                                                       |
    | <linkname> -> <targetfile> | Symbolic link with the name <linkname> pointing to <targetfile> |

    Returns the repo root as a string, ready to hand to a scan processor.
    """
    base_path.mkdir(parents=True, exist_ok=True)
    for item in specification.splitlines():
        if item.startswith("#") or item.strip() == "":
            continue
        if item.strip().endswith("/"):
            (base_path / item.strip()).mkdir(parents=True, exist_ok=True)
        elif "->" in item:
            link_name, target_file = item.strip().split("->")
            os.symlink(target_file.strip(), base_path / link_name.strip())
        else:
            file_content = "Created for testing only"
            if ":" in item:
                file_name, file_content = item.strip().split(":")
            else:
                file_name = item.strip()
            file_path = base_path / file_name.strip()
            file_path.write_text(file_content.strip() + "\r\n", encoding="utf-8")

    return str(base_path)


def create_random_repo_structure(
    base_path: Path,
    depth: int = 3,
    dir_count: int = 5,
    file_count: int = 10,
    max_file_size: int = 1024,
) -> str:
    """Recursively create a directory tree with random files below base_path.

    Returns the repo root as a string, ready to hand to a scan processor.
    """

    def random_name(length: int = 8) -> str:
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def create_files_in_dir(path: Path, num_files: int, max_file_size: int):
        for _ in range(num_files):
            file_name = random_name() + ".txt"
            file_path = path / file_name
            content = "".join(
                random.choices(
                    string.ascii_letters + string.digits,
                    k=random.randint(1, max_file_size),
                )
            )
            file_path.write_text(content)

    def create_dirs(base_path: Path, depth: int, num_dirs: int, num_files: int):
        if depth == 0:
            create_files_in_dir(base_path, num_files, max_file_size)
            return

        for _ in range(num_dirs):
            dir_name = random_name()
            dir_path = base_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            create_dirs(dir_path, depth - 1, num_dirs, num_files)

    base_path.mkdir(parents=True, exist_ok=True)
    create_dirs(base_path, depth, dir_count, file_count)

    return str(base_path)


@dataclass(frozen=True)
class TreeShape:
    """How a tree built by :func:`create_large_repo_structure` is shaped.

    ``branching[depth]`` is the number of child directories a directory at that
    depth gets, so the length of ``branching`` is how deep the tree may grow.

    ``file_names`` is called with the number of files that still fit in the
    directory being filled and returns the names to create there. It must
    return at least one name and no more than it was asked for, which lets a
    caller keep files that belong together -- a source and the header its
    companion rule requires, say -- in the same directory.
    """

    branching: tuple[int, ...]
    file_names: Callable[[int], list[str]]
    dir_prefix: str = "dir"
    files_per_directory: tuple[int, int] = (4, 10)
    seed: int = 0


_CREATE_FILE_FLAGS = os.O_CREAT | os.O_WRONLY | os.O_TRUNC


def create_large_repo_structure(
    base_path: Path, shape: TreeShape, file_budget: int
) -> str:
    """Create a tree below base_path holding exactly file_budget files.

    Directories are filled breadth first and are created only once the budget
    reaches them, so the tree grows as deep as ``shape.branching`` allows and
    leaves no empty directory behind. Each level is filled in shuffled order,
    which scatters the partially filled deepest level across the whole tree
    instead of packing it under the first few parents.

    Files are created empty -- a scan looks at names, never at content.

    Returns the repo root as a string, ready to hand to a scan processor.

    Exceptions:
        ValueError: Raised when the shape holds too few directories for the
            budget, or when ``file_names`` breaks its contract.
    """
    base_path.mkdir(parents=True, exist_ok=True)
    rng = random.Random(shape.seed)
    fewest, most = shape.files_per_directory

    remaining = file_budget
    depth = 0
    # base_path exists already, so the first level is filled, not created.
    level = [str(base_path)]

    while level and remaining > 0:
        rng.shuffle(level)
        for directory in level:
            if remaining <= 0:
                break
            if depth > 0:
                os.mkdir(directory)
            remaining -= _fill_directory(
                directory, shape.file_names, min(rng.randint(fewest, most), remaining)
            )
        if remaining <= 0 or depth == len(shape.branching):
            break
        level = _plan_child_directories(
            level, shape.dir_prefix, shape.branching[depth], remaining // fewest + 1
        )
        depth += 1

    if remaining > 0:
        raise ValueError(
            f"Tree shape holds too few directories for {file_budget} files: "
            f"{remaining} could not be placed"
        )

    return str(base_path)


def _fill_directory(
    directory: str, file_names: Callable[[int], list[str]], count: int
) -> int:
    """Create up to count files in directory and return how many were created."""
    names = file_names(count)
    if not 1 <= len(names) <= count:
        raise ValueError(
            f"file_names asked for {count} name(s) returned {len(names)}: {names}"
        )
    for name in names:
        os.close(os.open(os.path.join(directory, name), _CREATE_FILE_FLAGS, 0o644))
    return len(names)


def _plan_child_directories(
    parents: Sequence[str], dir_prefix: str, width: int, limit: int
) -> list[str]:
    """Name the next level's directories, capped at what the budget can fill.

    Nothing is created here: a planned directory the budget never reaches stays
    a string. ``parents`` is already in random order, so the cap drops a random
    selection of parents rather than one whole side of the tree.
    """
    return list(
        islice(
            (
                os.path.join(parent, f"{dir_prefix}_{index:02d}")
                for parent in parents
                for index in range(width)
            ),
            limit,
        )
    )
