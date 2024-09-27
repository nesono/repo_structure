# Repo Structure

A tool to maintain and enforce a clean and organized repository structure.

You can control:

- Specify which files and directories must be part of the repository
- Support required or optional entries (`required` vs `optional`)
- Specifications using Python regular expressions
- Mapping directory structure rules to specific directories (`directory_mapping`)
- Reusing directory structure rules recursively (`use_rule` in `structure_rules`)

Here is an example file that showcases all the supported features:
[example YAML](repo_structure_config.yaml)

## System Requirements

- Python 3.11
- [Pip requirements](requirements.in)

## Building from Source

### Using Bazel

- Install Bazelisk
- Run `bazel test`

### Using Python Venv

- `python3.11 -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements_lock.txt`
- `pytest *_test.py`

### Using Conda

- `conda create -n <conda_env> python=3.11`
- `conda activate <conda_env>`
- `pip install -r requirements_lock.txt`
- `pytest *_test.py`
