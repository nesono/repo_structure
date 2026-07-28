"""Library functions for repo structure testing.

The helpers here build repository trees below a caller-supplied directory —
typically pytest's ``tmp_path`` fixture — and return that directory. Nothing
changes the process CWD, so tests must pass the returned path into the API
under test.
"""

import os
from pathlib import Path
import random
import string


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
