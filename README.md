# Repo Structure

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

A tool to maintain and enforce a clean and organized repository structure.

You can control:

- Specify which files and directories must be part of the repository
- Support required or optional entries (`required` vs `optional`)
- Specifications using Python regular expressions
- Mapping directory structure rules to specific directories (`directory_map`)
- Reusing directory structure rules recursively (`use_rule` in `structure_rules`)
- Template for structures with patterns (`templates`)

Here is an example file that showcases all the supported features:
[example YAML](repo_structure.yaml)

Note that Windows clients are not supported at the moment.

## Integration

### Quick Start

The Repo Structure tool is written to be consumed through [pre-commit.com](https://pre-commit.com/).
A basic consumption looks like the following.

```yaml
repos:
  - repo: https://github.com/nesono/repo_structure
    rev: "v0.1.0"
    hooks:
      - id: repo-structure-diff-scan
```

The default configuration expects the file `repo_structure.yaml` in your
repository root. If you want to customize that, you need to add an `args` key
to the yaml, for instance:

```yaml
repos:
  - repo: https://github.com/nesono/repo_structure
    rev: "v0.1.0"
    hooks:
      - id: repo-structure-diff-scan
        args: ["--config-path", "path/to/your_config_file.yaml"]
```

## Available Repo Check Modes

The following modes are available with Repo Structure:

| ID | Description | Default stages |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------ | |
| `repo-structure-diff-scan` | Ensure that all added or modified files are allowed by the repo structure configuration | all |
| `repo-structure-diff-scan-debug` | Ensure that all added or modified files are allowed by the repo structure configuration with tracing enabled | all |
| `repo-structure-full-scan` | Run a full scan ensuring that all allowed and required files exist | `pre-push` |
| `repo-structure-full-scan-debug` | Run a full scan ensuring that all allowed and required files exist with tracing enabled | `pre-push` |

## Configuration Overall structure

The configuration files consists of three sections:

- Structure Rules (`structure_rules`), containing specific directory content
  rules
- Templates (`templates`), containing templates that generate structure rules
  using patterns
- Directory Map (`directory_map`), mapping the rules and templates to
  directories in the repository

In short, you use Structure Rules (and/or Templates) in the repository to
create parts of a prescribed directory structure and then map those rules to
directories.

## Structure Rules

Structure rules are specified within the `structure_rules` section in the yaml
configuration file.

**Nota Bene**: The names of structure rules must
(`example_rule_with_recursion`) not start with a '`__`', since this is reserved
for expanded templates.

### Files

For example, the following snippet declares a rule called `example_rule` that
requires a `BUILD` file, a `main.py` file and allows other `*.py` files to
coexist in the same directory.

```yaml
structure_rules:
  example_rule:
    - p: "LICENSE"
    - p: "BUILD"
      required: True
    - p: 'main\.py'
    - p: '[^/]*\.py'
      required: False
```

Note that each entry requires a key 'p' which contains a regex pattern, for the
directory entry it matches. An additional key 'required' can be used to specify
if the entry is required (default) or optional.

Thus, in our example above, `LICENSE`, `BUILD`, and `main.py` files are
required, whereas any Python file in the same directory is optional (allowed,
but not necessary).

### Directories

Directories are specified in Structure Rules using a trailing slash '/', for
instance

```yaml
structure_rules:
  example_rule_with_directory:
    - p: "LICENSE"
    - p: "BUILD"
      required: True
    - p: "main.py"
    - p: "library/"
      required: False
      if_exists:
        - p: 'lib\.py'
        - p: '[^/]*\.py'
          required: False
```

Here, we allow a subdirectory 'library' to exist. We require the file
'library/lib.py' if the folder 'library' exists. Any other file ending on '.py'
is allowed in it as well, but not required.

### Recursion

A Structure Rule may reuse itself (recursive directory structures) by using a
key 'use_rule', for example:

```yaml
structure_rules:
  example_rule_with_recursion:
    - p: "main.py"
    - p: '[^/]*\.py'
      required: False
    - p: "library/"
      use_rule: example_rule_with_recursion
```

## Templates

Templates provide the ability to reuse patterns of directory structures and
thereby reduce duplication in structure rules. Templates are expanded during
parsing and will populate the directory map and structure rules as if they
were specified in their expanded state.

The following example shows a simple template specification

```yaml
templates:
  example_template:
    - p: "{{component}}/"
    - p: "{{component}}/{{component}}_component.py"
    - p: "{{component}}/doc/"
    - p: "{{component}}/doc/{{component}}.techspec.md"
directory_map:
  /:
    - use_template: example_template
      component: ["lidar", "driver"]
```

During parsing, the template parameter `component` will be expanded to what
is provided in the `use_template` section in the `directory_map`.

The example would call this directory structure as compliant:

```console
lidar/
lidar/lidar_component.py
lidar/doc/
lidar/doc/lidar.techspec.md
driver/
driver/driver_component.py
driver/doc/
driver/doc/driver.techspec.md
```

Note that the expansion lists can have different lengths and the expansion
will permutate through the expansion lists. For example:

```yaml
templates:
  example_template:
    - p: "{{component}}/"
    - p: "{{component}}/{{component}}_component.{{extension}}"
    - p: "{{component}}/doc/"
    - p: "{{component}}/doc/{{component}}.techspec.md"
directory_map:
  /:
    - use_template: example_template
      component: ["lidar", "driver"]
      extension: ["rs"]
  /subdir/:
    - use_template: example_template
      component: ["control", "camera"]
      extension: ["py"]
```

Here, the suffixes will be reused for both component extensions.

## Directory Map

A directory map is a dictionary that maps directories (not patterns!) to
Structure Rules. One directory can require multiple Structure Rules using the
'use_rule' key.

The root key '/' must be in the Dictionary Map. A key must start and end with a
slash '/' and must point to a real directory in the repository.

A mapped directory only requires the Structure Rules that are mapped to it, it
**does not inherit** the rules from its parent directories.

For example:

```yaml
structure_rules:
  basic_rule:
    - p: "LICENSE"
    - p: "BUILD"
  python_main:
    - p: 'main\.py'
    - p: '[^/]*\.py'
      required: False
  python_library:
    - p: 'lib\.py'
    - p: '[^/]*\.py'
      required: False
    - p: "[^/]*/"
      required: False
      # allow library recursion
      use_rule: python_library
directory_map:
"/":
  - use_rule: basic_rule
"/python/":
  - use_rule: python_main
  - use_rule: python_library
```

## System Requirements

- Python 3.11 or 3.12
- [Pip requirements](requirements.txt)

## Building from Source

### Using Poetry

- `poetry install`
- `poetry run pytest`

### Using Python Venv

- `python3.11 -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`
- `pytest *_test.py`

### Using Conda

- `conda create -n .conda_env python=3.11`
- `conda activate .conda_env`
- `pip install -r requirements.txt`
- `pytest *_test.py`
