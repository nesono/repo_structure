"""A benchmark over a repository large enough for the numbers to mean something.

The tree built here holds two million files, which takes minutes to materialize
and minutes more to scan -- far too slow for the pull-request CI matrix. It is
marked ``heavy`` and deselected by the ``addopts`` in pyproject.toml, so only
the post-merge benchmark workflow (and an explicit ``pytest -m heavy``) runs it.

The generated repository deliberately uses every configuration feature the tool
has, so the numbers cover what a real scan costs rather than what the cheapest
possible rule set costs:

| Feature                        | Where it shows up in the generated tree      |
| ------------------------------ | -------------------------------------------- |
| `require` / `allow` / `forbid` | the root rule and every recursive rule       |
| `use_rule` recursion           | `packages/`, `libs/`, `notes/`, `frontend/`  |
| `if_exists`                    | `docs/` below the root rule                  |
| `companion` + `{{capture}}`    | `libs/`, where every `.cpp` needs its `.h`   |
| `templates` + `parameters`     | `components/`, one directory per component   |
| builtin `ignore` rule          | `third_party/`                               |
| `.gitignore`                   | `build_output/` and `debug.log`              |
| `use_config`                   | `frontend/`, which owns its own rules        |
| `inherit` + `override`         | `frontend/`, reusing and redefining root rules |
| symlinks (not followed)        | `packages/`                                  |
| hidden entries (included)      | `.editorconfig`                              |

Set ``REPO_STRUCTURE_BENCHMARK_FILES`` to a smaller number to build a scaled
down version of the same repository -- useful for checking the configuration
still describes the tree without waiting for the full run.
"""

import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterator

import pytest

from .config import Configuration
from .diff_scan import DiffScanProcessor
from .full_scan import FullScanProcessor
from .models import Flags, ScanIssue, ScanResult
from .test_lib import TreeShape, create_large_repo_structure, create_repo_structure

pytestmark = pytest.mark.heavy


_TOTAL_FILES: Final = int(os.environ.get("REPO_STRUCTURE_BENCHMARK_FILES", "2000000"))

# How often each scan is repeated. A full scan round re-walks the whole tree,
# so it trades wall clock for a trustworthy minimum; a diff scan round is cheap
# enough to afford more of them.
_SCAN_ROUNDS: Final = 3
_DIFF_ROUNDS: Final = 10

# The scan flags the CLI defaults to: symlinks are not followed, hidden entries
# are checked like any other.
_FLAGS: Final = Flags(follow_symlinks=False, include_hidden=True)

_ROOT_CONFIG: Final = r"""
structure_rules:
  base_structure:
    - description: 'Files every repository carries'
    - require: 'README\.md'
    - require: 'LICENSE'
    - require: '\.editorconfig'
    - forbid: '.*\.orig'
    - allow: 'CHANGELOG\.md'
    - allow: 'docs/'
      if_exists:
        - require: 'index\.md'
        - allow: '.*\.md'
  markdown_docs:
    - description: 'A tree of markdown documents'
    - require: 'index\.md'
    - allow: 'note_.*\.md'
    - allow: '.*/'
      use_rule: markdown_docs
  package_tree:
    - description: 'Recursive python package tree'
    - require: 'main\.py'
    - forbid: '.*\.pyc'
    - allow: 'module_.*\.py'
    - allow: '.*/'
      use_rule: package_tree
  cpp_library:
    - description: 'C++ sources, each with the header it needs beside it'
    - allow: '.*\.h'
    - allow: '(?P<base>.*)\.cpp'
      companion:
        - require: '{{base}}\.h'
        - allow: '{{base}}\.md'
    - allow: '.*/'
      use_rule: cpp_library
templates:
  component_template:
    - description: 'One directory per component, each with its tech spec'
    - require: '{{component}}/'
      if_exists:
        - require: '{{component}}_component\.{{extension}}'
        - require: 'doc/'
          if_exists:
            - require: '{{component}}\.techspec\.md'
directory_map:
  /:
    - description: 'Repository root'
    - use_rule: base_structure
  /components/:
    - description: 'Components, expanded from a template'
    - use_template: component_template
      parameters:
        component: ['lidar', 'driver', 'camera']
        extension: ['py']
  /libs/:
    - description: 'C++ libraries whose sources require companion headers'
    - use_rule: cpp_library
  /notes/:
    - description: 'Markdown notes'
    - use_rule: markdown_docs
  /packages/:
    - description: 'The bulk of the repository'
    - use_rule: package_tree
  /third_party/:
    - description: 'Vendored code, not ours to validate'
    - use_rule: ignore
  /frontend/:
    - description: 'Owned by the frontend team, governed by its own file'
    - use_config: repo_structure.yaml
"""

_FRONTEND_CONFIG: Final = r"""
inherit:
  structure_rules: all
  override: [markdown_docs]
structure_rules:
  ts_package:
    - description: 'Recursive TypeScript package tree'
    - require: 'index\.ts'
    - allow: 'component_.*\.ts'
    - allow: '.*/'
      use_rule: ts_package
  markdown_docs:
    - description: "The frontend's own flavour of docs"
    - require: 'GUIDE\.md'
    - allow: 'note_.*\.md'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: ts_package
  /docs/:
    - description: 'Frontend docs, from the overridden rule'
    - use_rule: markdown_docs
  /scripts/:
    - description: 'Python helpers, from the rule inherited from the root'
    - use_rule: package_tree
"""

_GITIGNORE: Final = "build_output/\n*.log\n"

# Everything the generated tree needs in a fixed place: the entries the root
# rule requires, the template's components, and the frontend's own docs.
_FIXED_ENTRIES: Final = """
README.md
LICENSE
.editorconfig
CHANGELOG.md
debug.log
docs/
docs/index.md
docs/architecture.md
docs/glossary.md
components/lidar/doc/
components/lidar/lidar_component.py
components/lidar/doc/lidar.techspec.md
components/driver/doc/
components/driver/driver_component.py
components/driver/doc/driver.techspec.md
components/camera/doc/
components/camera/camera_component.py
components/camera/doc/camera.techspec.md
frontend/docs/
frontend/docs/GUIDE.md
frontend/docs/note_01.md
frontend/docs/note_02.md
"""

# Created once the tree they point into exists. Both are skipped by the scan,
# since the flags say not to follow symlinks.
_SYMLINK_ENTRIES: Final = """
packages/legacy_main.py -> main.py
packages/legacy -> pkg_00
"""


def _python_module_names(count: int) -> list[str]:
    """A package directory: the main module the rule requires, plus modules."""
    return ["main.py"] + [f"module_{index:02d}.py" for index in range(count - 1)]


def _typescript_names(count: int) -> list[str]:
    """A frontend directory: the index the rule requires, plus components."""
    return ["index.ts"] + [f"component_{index:02d}.ts" for index in range(count - 1)]


def _cpp_pair_names(count: int) -> list[str]:
    """Sources paired with the headers their companion rule requires.

    An odd count ends on a lone header, which needs no companion of its own.
    """
    names = [
        f"mod_{index:02d}{extension}"
        for index in range(count // 2)
        for extension in (".cpp", ".h")
    ]
    if count % 2:
        names.append(f"mod_{count // 2:02d}.h")
    return names


def _markdown_names(count: int) -> list[str]:
    """A notes directory: the index the rule requires, plus notes."""
    return ["index.md"] + [f"note_{index:02d}.md" for index in range(count - 1)]


def _opaque_names(count: int) -> list[str]:
    """Files in a subtree no rule ever looks at, so the names do not matter."""
    return [f"blob_{index:02d}.bin" for index in range(count)]


@dataclass(frozen=True)
class _Subtree:
    """One generated part of the benchmark repository."""

    path: str
    shape: TreeShape
    files: int


_FRONTEND_FILES: Final = max(1, _TOTAL_FILES // 4)
_SCRIPT_FILES: Final = max(1, _TOTAL_FILES // 100)
_LIB_FILES: Final = max(2, _TOTAL_FILES // 40)
_NOTE_FILES: Final = max(1, _TOTAL_FILES // 2000)
_VENDORED_FILES: Final = max(1, _TOTAL_FILES // 10000)
_IGNORED_FILES: Final = max(1, _TOTAL_FILES // 20000)
# The recursive python tree takes whatever the named subtrees do not claim, so
# the totals add up to _TOTAL_FILES however the shares are tuned.
_PACKAGE_FILES: Final = max(
    1,
    _TOTAL_FILES
    - (
        _FRONTEND_FILES
        + _SCRIPT_FILES
        + _LIB_FILES
        + _NOTE_FILES
        + _VENDORED_FILES
        + _IGNORED_FILES
    ),
)

# Every branching sequence is sized with room to spare: a shape that cannot
# hold its budget raises rather than quietly building a smaller tree.
_SUBTREES: Final = (
    _Subtree(
        "packages",
        TreeShape(
            branching=(10, 9, 8, 7, 7, 8),
            file_names=_python_module_names,
            dir_prefix="pkg",
            seed=1,
        ),
        _PACKAGE_FILES,
    ),
    _Subtree(
        "frontend",
        TreeShape(
            branching=(12, 10, 9, 9, 9),
            file_names=_typescript_names,
            dir_prefix="ui",
            seed=2,
        ),
        _FRONTEND_FILES,
    ),
    _Subtree(
        "frontend/scripts",
        TreeShape(
            branching=(8, 8, 8, 8),
            file_names=_python_module_names,
            dir_prefix="tool",
            seed=3,
        ),
        _SCRIPT_FILES,
    ),
    _Subtree(
        "libs",
        TreeShape(
            branching=(10, 10, 10, 10),
            file_names=_cpp_pair_names,
            dir_prefix="lib",
            seed=4,
        ),
        _LIB_FILES,
    ),
    _Subtree(
        "notes",
        TreeShape(
            branching=(6, 6, 6),
            file_names=_markdown_names,
            dir_prefix="topic",
            seed=5,
        ),
        _NOTE_FILES,
    ),
    _Subtree(
        "third_party",
        TreeShape(
            branching=(6, 6, 6), file_names=_opaque_names, dir_prefix="dep", seed=6
        ),
        _VENDORED_FILES,
    ),
    _Subtree(
        "build_output",
        TreeShape(
            branching=(5, 5, 5), file_names=_opaque_names, dir_prefix="out", seed=7
        ),
        _IGNORED_FILES,
    ),
)

# One in this many files is kept as a diff-scan subject. Sampled only from the
# subtrees the scan governs: a diff scan is handed paths git reports as changed,
# so it never consults .gitignore and must not be fed ignored paths.
_DIFF_SAMPLE_RATE: Final = 4096
_DIFF_SAMPLE_PREFIXES: Final = ("packages/", "frontend/", "libs/", "notes/")


@dataclass(frozen=True)
class _HeavyRepo:
    """The generated repository, and what it took to put it on disk."""

    root: str
    files: int
    directories: int
    changed_paths: list[str]
    setup_seconds: float

    @property
    def entries(self) -> int:
        """Files plus directories -- what a full scan has to look at."""
        return self.files + self.directories


def _materialize(root: Path) -> None:
    """Write the whole benchmark repository below root."""
    create_repo_structure(root, _FIXED_ENTRIES)
    (root / ".gitignore").write_text(_GITIGNORE, encoding="utf-8")
    (root / "repo_structure.yaml").write_text(_ROOT_CONFIG, encoding="utf-8")
    (root / "frontend" / "repo_structure.yaml").write_text(
        _FRONTEND_CONFIG, encoding="utf-8"
    )
    for subtree in _SUBTREES:
        create_large_repo_structure(root / subtree.path, subtree.shape, subtree.files)
    create_repo_structure(root, _SYMLINK_ENTRIES)


def _survey(root: Path) -> tuple[int, int, list[str]]:
    """Count what landed on disk and sample paths for the diff scan.

    Counting by walking keeps the reported size honest -- it is whatever the
    filesystem holds, not what the generator meant to write.
    """
    files = 0
    directories = 0
    changed_paths: list[str] = []
    prefix_length = len(str(root)) + 1

    for parent, child_directories, child_files in os.walk(root):
        directories += len(child_directories)
        relative_parent = parent[prefix_length:].replace(os.sep, "/")
        sampled = relative_parent.startswith(_DIFF_SAMPLE_PREFIXES)
        for name in child_files:
            files += 1
            if sampled and files % _DIFF_SAMPLE_RATE == 0:
                changed_paths.append(f"{relative_parent}/{name}")

    return files, directories, changed_paths


@pytest.fixture(name="heavy_repo", scope="session")
def fixture_heavy_repo(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[_HeavyRepo]:
    """Build the benchmark repository once and remove it afterwards.

    Session scoped because materializing it costs minutes, and removed on the
    way out because it costs gigabytes.
    """
    root = tmp_path_factory.mktemp("heavy_repo")
    started = time.perf_counter()
    _materialize(root)
    setup_seconds = time.perf_counter() - started

    files, directories, changed_paths = _survey(root)
    yield _HeavyRepo(
        root=str(root),
        files=files,
        directories=directories,
        changed_paths=changed_paths,
        setup_seconds=setup_seconds,
    )

    shutil.rmtree(root, ignore_errors=True)


def _configuration(repo: _HeavyRepo) -> Configuration:
    return Configuration.from_file(os.path.join(repo.root, "repo_structure.yaml"))


def _summarize(issues: list[ScanIssue], limit: int = 5) -> str:
    """Describe issues without pasting a million of them into the report."""
    head = "\n".join(
        f"  {issue.path}: {issue.message.strip()}" for issue in issues[:limit]
    )
    tail = f"\n  ... and {len(issues) - limit} more" if len(issues) > limit else ""
    return f"{len(issues)} issue(s):\n{head}{tail}"


def _assert_clean(result: ScanResult) -> None:
    """Fail loudly if the configuration stopped describing the tree.

    Without this the benchmark would silently switch to measuring how fast the
    tool reports two million unspecified entries.
    """
    assert result.is_success, _summarize(result.errors)
    assert not result.warnings, _summarize(result.warnings)


def _publish(
    request: pytest.FixtureRequest, heading: str, measurements: list[tuple[str, str]]
) -> None:
    """Report measurements where somebody will actually see them.

    Terminal output goes through the terminal reporter rather than print, since
    pytest captures whatever a test writes to stdout. On GitHub Actions the
    same numbers are appended to the job summary, so a post-merge run shows
    them on the run's front page instead of burying them in the log.
    """
    terminal = request.config.pluginmanager.getplugin("terminalreporter")
    if terminal is not None:
        terminal.write_line(heading)
        for label, value in measurements:
            terminal.write_line(f"  {label:<28}{value}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    rows = "".join(f"| {label} | {value} |\n" for label, value in measurements)
    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write(
            f"## {heading}\n\n| Measurement | Value |\n| --- | --- |\n{rows}\n"
        )


def test_benchmark_full_scan_of_a_huge_repository(
    benchmark, heavy_repo: _HeavyRepo, request: pytest.FixtureRequest
) -> None:
    """Measure a full scan of a two million file repository."""
    processor = FullScanProcessor(heavy_repo.root, _configuration(heavy_repo), _FLAGS)

    result = benchmark.pedantic(processor.scan, rounds=_SCAN_ROUNDS)
    _assert_clean(result)

    seconds = benchmark.stats.stats.min
    entries_per_second = heavy_repo.entries / seconds
    benchmark.extra_info.update(
        {
            "files": heavy_repo.files,
            "directories": heavy_repo.directories,
            "entries": heavy_repo.entries,
            "setup_seconds": round(heavy_repo.setup_seconds, 2),
            "entries_per_second": round(entries_per_second),
        }
    )
    _publish(
        request,
        "Full scan of a huge repository",
        [
            ("Files", f"{heavy_repo.files:,}"),
            ("Directories", f"{heavy_repo.directories:,}"),
            ("Entries scanned", f"{heavy_repo.entries:,}"),
            ("Tree materialized in", f"{heavy_repo.setup_seconds:,.1f} s"),
            (f"Scan, best of {_SCAN_ROUNDS}", f"{seconds:,.2f} s"),
            ("Throughput", f"{entries_per_second:,.0f} entries/s"),
        ],
    )


def test_benchmark_diff_scan_of_a_huge_repository(
    benchmark, heavy_repo: _HeavyRepo, request: pytest.FixtureRequest
) -> None:
    """Measure a diff scan, which should cost what the change costs, not the repo.

    Same repository as the full scan above, so the two numbers say how much a
    pre-commit hook saves by checking only what changed.
    """
    processor = DiffScanProcessor(
        _configuration(heavy_repo), _FLAGS, repo_root=heavy_repo.root
    )
    paths = heavy_repo.changed_paths
    assert paths, "the survey found no paths to hand to the diff scan"

    result = benchmark.pedantic(
        processor.check_paths, args=(paths,), rounds=_DIFF_ROUNDS
    )
    _assert_clean(result)

    seconds = benchmark.stats.stats.min
    paths_per_second = len(paths) / seconds
    benchmark.extra_info.update(
        {
            "paths": len(paths),
            "entries": heavy_repo.entries,
            "paths_per_second": round(paths_per_second),
        }
    )
    _publish(
        request,
        "Diff scan of the same repository",
        [
            ("Paths checked", f"{len(paths):,}"),
            ("Entries in the repository", f"{heavy_repo.entries:,}"),
            (f"Scan, best of {_DIFF_ROUNDS}", f"{seconds * 1000:,.1f} ms"),
            ("Throughput", f"{paths_per_second:,.0f} paths/s"),
        ],
    )
