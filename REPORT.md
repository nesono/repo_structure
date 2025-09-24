# Repository Structure Report

Generated on: 2025-09-24 10:32:07

This document describes the enforced repository structure rules and directory mappings.

## Table of Contents

- [Directory Mappings](#directory-mappings)
- [Structure Rules](#structure-rules)
- [Rule Details](#rule-details)

## Directory Mappings

The following directories have structure rules applied:

| Directory | Applied Rules |
|-----------|---------------|
| `/` | `base_structure` |
| `/repo_structure/` | `python_package` |
| `/.github/` | `ignore` |

## Structure Rules

The following structure rules are defined:

- [`base_structure`](#rule-base-structure)
- [`python_package`](#rule-python-package)

## Rule Details

### Rule: `base_structure`

#### Required Files

- `environment.yml`
- `requirements.txt`
- `LICENSE`
- `README\.md`
- `PUBLISHING\.md`
- `conflicting_test_config\.yaml`
- `\.pre-commit-config\.yaml`
- `\.pre-commit-hooks\.yaml`
- `\.markdownlint\.yaml`
- `pyproject\.toml`
- `repo_structure\.iml`
- `renovate\.json`
- `\.python-version`

#### Examples

- `LICENSE` - File (✅ Required)
- `README.md` - File (✅ Required)
- `PUBLISHING.md` - File (✅ Required)
- `conflicting_test_config.yaml` - File (✅ Required)
- `pyproject.toml` - File (✅ Required)
- `repo_structure.iml` - File (✅ Required)
- `renovate.json` - File (✅ Required)
- `.python-version` - File (✅ Required)

### Rule: `python_package`

#### Required Files

- `__main__\.py`
- `__init__\.py`
- `.*\.py`
- `config\.schema\.json`
- `test_config_.*\.yaml`

#### Examples

- `__main__.py` - File (✅ Required)
- `__init__.py` - File (✅ Required)
- `example.py` - File (✅ Required)
- `test_config_example.yaml` - File (✅ Required)

---

*This report was automatically generated from the repository structure configuration.*
