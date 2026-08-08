# CLAUDE.md

`repo_structure` is a CLI + pre-commit hook that validates a repository's
directory structure against a YAML config. It validates _itself_ — see
"Self-validation" below.

## Commands

```sh
uv run --extra dev pytest          # test suite
uv run prek run --all-files        # lint / format / type checks
uv run repo_structure full-scan    # validate this repo against repo_structure.yaml
```

Always run checks through `prek`, never ad-hoc `black` / `ruff` / `pylint` /
`mypy` — `prek` owns the pinned versions and hook order.

## Layout conventions

**Tests live next to the code they test.** `config.py` and `config_test.py` sit
in the same directory. Do not propose or implement a move to a top-level
`tests/` directory, even though that is the more common Python convention, and
even if an open issue asks for it.

This is load-bearing, not just taste: `repo_structure.yaml` uses a `companion`
rule requiring `{{base}}_test\.py` beside each module, which is this repo's own
demo of the tool's flagship feature. `check_companion_files` resolves companions
by walking _below_ the matched file's directory, so a `../tests/…` companion can
never match — relocating tests forces that rule to be dropped.

Tests are kept out of the wheel at _build_ time instead of by relocating them.
The build backend is hatchling (with `hatch-vcs` for the version), whose
`[tool.hatch.build.targets.wheel] exclude` matches file patterns. setuptools
could not do this: its `packages.find` exclude filters _package names_, not
files, so the old `exclude = ["repo_structure/*_test.py"]` line was inert.

Anything test-only added under `repo_structure/` must therefore match one of
the `exclude` patterns in `pyproject.toml` — `*_test.py`, `test_lib.py`,
`test_config_*.yaml` — or it will ship to PyPI. The sdist deliberately keeps
the tests so downstreams can run the suite.

## Module map

- `__main__.py` — click CLI: `full-scan`, `diff-scan`, `report`
- `config.py` — YAML parsing, schema validation, template expansion
- `config_merge.py` — flattens a `use_config` mount tree into one configuration:
  rule-name qualification, `inherit`/`override`, collision errors. Takes the
  document parser as a callable so `config.py` can depend on it, not vice versa
- `models.py` — dataclasses, type aliases, rule constants
- `errors.py` — exception hierarchy
- `paths.py` — path normalization
- `patterns.py` — capture extraction, `{{name}}` template substitution
- `scanning.py` — entry skipping, matching, companion checks, backlog building
- `full_scan.py` / `diff_scan.py` — the two scan processors
- `report.py` — report generation and text/json/markdown formatting
- `schema.py` — loads `config.schema.json`
- `test_lib.py` — test-only helpers (tmpdir repo fixtures)
- `repo_structure_lib.py` — deprecated re-export shim; import from the focused
  modules directly

## Self-validation

`repo_structure.yaml` describes this repository, and `full-scan` runs in CI and
as a pre-commit hook. Its `base_structure` rule has no catch-all `allow`, so
**adding any new file at the repo root fails the scan until you add a matching
entry to `repo_structure.yaml`**. The same applies to new directories, which
need a `directory_map` entry. Run `uv run repo_structure full-scan` after adding
files.

## Issue-driven work

Issues are often phased (`Phase N.M: …`) and were drafted from a cleanup plan.
Verify an issue's stated premise against the code before implementing it — at
least one has been closed as not-planned because its rationale did not hold.
