"""Library functions for repo structure testing."""

import os
import shutil
import tempfile
from typing import Callable, TypeVar
from pathlib import Path
import random
import string
import functools


def _get_tmp_dir() -> str:
    return tempfile.mkdtemp()


def _remove_tmp_dir(tmpdir: str) -> None:
    shutil.rmtree(tmpdir)


def _create_repo_directory_structure(specification: str) -> None:
    """Creates a directory structure based on a specification file.
    Must be run in the target directory.

    A specification file can contain the following entries:
    | Entry                      | Meaning                                                         |
    | # <string>                 | comment string (ignored in output)                              |
    | <filename>:<content>       | File with content <content> (single line only)                  |
    | <dirname>/                 | Directory                                                       |
    | <linkname> -> <targetfile> | Symbolic link with the name <linkname> pointing to <targetfile> |
    """
    for item in iter(specification.splitlines()):
        if item.startswith("#") or item.strip() == "":
            continue
        if item.strip().endswith("/"):
            os.makedirs(item.strip(), exist_ok=True)
        elif "->" in item:
            link_name, target_file = item.strip().split("->")
            os.symlink(target_file.strip(), link_name.strip())
        else:
            file_content = "Created for testing only"
            if ":" in item:
                file_name, file_content = item.strip().split(":")
            else:
                file_name = item.strip()
            with open(file_name.strip(), "w", encoding="utf-8") as f:
                f.write(file_content.strip() + "\r\n")


def _clear_repo_directory_structure() -> None:
    for root, dirs, files in os.walk(".", topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))


R = TypeVar("R")


def with_repo_structure_in_tmpdir(specification: str):
    """Create and remove repo structure based on specification for testing. Use as decorator."""

    def decorator(func: Callable[..., R]) -> Callable[..., R]:

        def wrapper(*args, **kwargs):
            cwd = os.getcwd()
            tmpdir = _get_tmp_dir()
            os.chdir(tmpdir)
            _create_repo_directory_structure(specification)
            try:
                result = func(*args, **kwargs)
            finally:
                _clear_repo_directory_structure()
                os.chdir(cwd)
                _remove_tmp_dir(tmpdir)
            return result

        return wrapper

    return decorator


def _create_random_file_tree(
    base_path: Path,
    depth: int = 3,
    dir_count: int = 5,
    file_count: int = 10,
    max_file_size: int = 1024,
):
    """Recursively create a directory tree with random files."""

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


def with_random_repo_structure_in_tmpdir(
    depth: int = 3, dir_count: int = 5, file_count: int = 10, max_file_size: int = 1024
):
    """Create and remove random repo structure based on specification for testing."""

    def decorator(func: Callable[..., R]) -> Callable[..., R]:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cwd = os.getcwd()
            tmpdir = _get_tmp_dir()
            os.chdir(tmpdir)
            _create_random_file_tree(
                Path(tmpdir), depth, dir_count, file_count, max_file_size
            )
            try:
                result = func(*args, **kwargs)
            finally:
                _clear_repo_directory_structure()
                os.chdir(cwd)
                _remove_tmp_dir(tmpdir)
            return result

        return wrapper

    return decorator
