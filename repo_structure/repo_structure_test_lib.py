import os
import shutil
import tempfile
from typing import Callable, TypeVar


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

