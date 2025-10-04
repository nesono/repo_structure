# Repo Structure

[![Build and Test CI](https://github.com/nesono/repo_structure/actions/workflows/build-and-test-ci.yaml/badge.svg)](https://github.com/nesono/repo_structure/actions/workflows/build-and-test-ci.yaml)
[![Pre-Commit.Com](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![CodeQL](https://github.com/nesono/repo_structure/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/nesono/repo_structure/actions/workflows/github-code-scanning/codeql)
[![Publish to PyPI](https://github.com/nesono/repo_structure/actions/workflows/publish-to-pypi.yaml/badge.svg)](https://github.com/nesono/repo_structure/actions/workflows/publish-to-pypi.yaml)

A tool to maintain and enforce a clean and organized repository structure.

You can control:

- Specify which files and directories must be part of the repository
- Support required, allowed, or forbidden entries (`require`, `allow`, `forbid`)
- Specifications using Python regular expressions
- Mapping directory structure rules to specific directories (`directory_map`)
- Reusing directory structure rules recursively (`use_rule` in `structure_rules`)
- Template for structures with patterns (`templates`)

Here is an example file that showcases all the supported features:
[example YAML](repo_structure.yaml)

Cross-platform support for Windows, macOS, and Linux.

## Integration

### Quick Start

The Repo Structure tool is written to be consumed through [pre-commit.com](https://pre-commit.com/) and/or via pip for running locally.

Installation with pip:

```bash
pip install repo-structure
```

On Windows, you can install using pip in Command Prompt, PowerShell, or Windows Terminal.
For Windows users using pre-commit, ensure you have Python and Git properly installed. The tool works seamlessly across Windows, macOS, and Linux with automatic path normalization.

A basic consumption with pre-commit looks like the following.

<!-- keep the versions in this document manually updated -->

```yaml
repos:
  - repo: https://github.com/nesono/repo_structure
    rev: ""
    hooks:
      - id: diff
```

### Custom Configuration File Path

The default configuration expects the file `repo_structure.yaml` in your
repository root. If you want to customize that, you need to add an `args` key
to the yaml, for instance:

```yaml
repos:
  - repo: https://github.com/nesono/repo_structure
    rev: ""
    hooks:
      - id: diff
        args: ["--config-path", "path/to/your_config_file.yaml"]
```

## Available Repo Check Modes

The following modes are available with Repo Structure:

| ID                   | Description                                                                                                      |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `diff`               | Ensure that all added or modified files are allowed by the repo structure configuration                          |
| `diff-debug`         | Ensure that all added or modified files are allowed by the repo structure configuration with tracing enabled     |
| `full`               | Run a full scan ensuring that all allowed and required files exist                                               |
| `full-debug`         | Run a full scan ensuring that all allowed and required files exist with tracing enabled                          |
| `full-warning`       | Run a full scan ensuring that all allowed and required files exist and warn of unused rules                      |
| `full-warning-debug` | Run a full scan ensuring that all allowed and required files exist and warn of unused rules with tracing enabled |

Note that the full scan hooks might take longer time than you are willing to spend during `pre-commit`.
You can enable then for the `pre-push` stage only, or you can run the tool in the terminal installed from pip.

## Configuration Report

You can generate a comprehensive report of your repository structure configuration that visualizes how directories are mapped to rules and what those rules enforce.

### Generating Reports

Generate reports using the command line:

```bash
repo_structure report --format markdown -o report.md
repo_structure report --format text -o report.txt
repo_structure report --format json -o report.json
```

By default, the report is output in text format to stdout. You can specify a custom configuration file:

```bash
repo_structure report --config-path path/to/config.yaml --format markdown -o report.md
```

### Report Contents

The report includes:

- **Repository Information**: Branch name, commit hash, and date
- **Directory Mappings**: Shows each directory and which structure rules apply to it
- **Structure Rules**: Details each rule's description, patterns, and which directories use it
- **Cross-references**: In markdown format, rules and directories are linked for easy navigation

### Example Markdown Report

The markdown report generates clickable links between directories and rules:

```markdown
## Directory Mappings

### Directory: `/` {#dir-root}

**Applied Rules:**

- [`base_structure`](#rule-base_structure): Core project files

## Structure Rules

### Rule: `base_structure` {#rule-base_structure}

**Patterns:**

- `require: LICENSE`
- `require: README\.md`

**Applied to Directories:**

- [`/`](#dir-root): Root directory
```

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
    - require: "BUILD"
    - require: 'main\.py'
    - allow: '.*\.py'
```

Note that each entry requires one the following keys: `require`, `allow`, or
`forbid`. The key needs to contains a regex pattern, for the directory
entry it matches.

### Directories

Directories are specified in Structure Rules using a trailing slash '/', for
instance

```yaml
structure_rules:
  example_rule_with_directory:
    - require: "LICENSE"
    - require: "BUILD"
    - require: "main\.py"
    - allow: "library/"
      if_exists:
        - require: 'lib\.py'
        - allow: '.*\.py'
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
    - require: "main\.py"
    - allow: "library/"
      use_rule: example_rule_with_recursion
```

Note that if you require a directory that uses the structure rule that in turn
requires entries the structure rule is not fulfillable. For instance, the
following would cause an error:

```yaml
structure_rules:
  example_rule_with_recursion:
    - require: "main\.py"
    - require: "library/"
      use_rule: example_rule_with_recursion
```

### Companion Files

Structure rules can enforce that certain files require companion files to exist. This is useful for ensuring that implementation files have corresponding headers, tests, or documentation.

Use the `requires_companion` keyword along with named capture groups in your patterns:

```yaml
structure_rules:
  cpp_with_headers:
    - description: "C++ files with required headers"
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: "{{base}}.h"
    - allow: '.*\.h'
directory_map:
  /src/:
    - description: "Source directory"
    - use_rule: cpp_with_headers
```

In this example:

- Any `.cpp` file must have a corresponding `.h` file with the same base name
- `widget.cpp` requires `widget.h` to exist
- `engine.cpp` requires `engine.h` to exist

#### Named Capture Groups

Companion files use Python regex named capture groups to extract parts of the filename:

- `(?P<name>pattern)` - Creates a named group that can be referenced in companion patterns
- `{{name}}` - Placeholder in companion pattern that gets replaced with the captured value

#### Multiple Companions

You can require multiple companion files:

```yaml
structure_rules:
  cpp_with_header_and_test:
    - description: "C++ files with headers and tests"
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: "{{base}}.h"
        - require: "{{base}}_test.cpp"
    - allow: '.*\.h'
    - allow: '.*_test\.cpp'
```

This ensures that `foo.cpp` requires both `foo.h` and `foo_test.cpp` to exist.

#### Optional Companions

Use `allow` instead of `require` for optional companion files:

```yaml
structure_rules:
  cpp_with_optional_docs:
    - description: "C++ with required header, optional docs"
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: "{{base}}.h"
        - allow: "{{base}}.md" # Optional documentation
    - allow: '.*\.h'
    - allow: '.*\.md'
```

#### Companions in Subdirectories

Companion files can be located in subdirectories by including path separators in the companion pattern:

```yaml
structure_rules:
  cpp_with_header_in_include:
    - description: "C++ with headers in include/ subdirectory"
    - allow: '(?P<base>.*)\.cpp'
      requires_companion:
        - require: "include/{{base}}.h"
    - allow: 'include/.*\.h'
directory_map:
  /src/:
    - description: "Source directory"
    - use_rule: cpp_with_header_in_include
```

This ensures that `src/widget.cpp` requires `src/include/widget.h` to exist.

## Pattern Matching Order

Patterns are matched in the order they are declared. Once a rule is matched,
the processing is stopped. Hence, wildcard patterns must be put to the end of
the structure rules. Or more precise:

> Less specific patterns need to come later that more specific patterns.

Keep this rule in the back of your head when designing the structure rules. You
won't get noticed if you make a mistake, unless you run into a directory
structure that happens to run into the issue.

For example, the following configuration would fail always

```yaml
structure_rules:
  example_rule:
    - require: ".*"
    - require: 'main\.py'
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
    - require: "{{component}}/"
      if_exists:
        - require: "{{component}}_component.py"
        - require: "doc/"
          if_exists:
            - require: "{{component}}.techspec.md"
directory_map:
  /:
    - use_template: example_template
      parameters:
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
    - require: "{{component}}/"
      if_exists:
        - require: "{{component}}_component.{{extension}}"
        - require: "doc/"
          if_exists:
            - require: "{{component}}.techspec.md"
directory_map:
  /:
    - use_template: example_template
      parameters:
        component: ["lidar", "driver"]
        extension: ["rs"]
  /subdir/:
    - use_template: example_template
      parameters:
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
    - require: "LICENSE"
    - require: "BUILD"
  python_main:
    - require: 'main\.py'
    - allow: '.*\.py'
  python_library:
    - require: 'lib\.py'
    - allow: '.*\.py'
    - allow: ".*/"
      # allow library recursion
      use_rule: python_library
directory_map:
/:
  - use_rule: basic_rule
/python/:
  - use_rule: python_main
  - use_rule: python_library
```

Ignoring a directory can be done using the built-in rule `ignore`. For example:

```yaml
tructure_rules:
  basic_rule:
    - require: "LICENSE"
    - require: "BUILD"
  python_main:
directory_map:
/:
  - use_rule: basic_rule
/python/:
  - use_rule: ignore
```

The rule can

## System Requirements

- Tested with Python versions ["3.10", "3.11", "3.12", "3.13", "3.14"]
- Dependencies defined in [pyproject.toml](pyproject.toml)
- Does not work on Windows

## Building from Source

### Using Poetry

- `poetry install`
- `poetry run pytest`

### Using Python Venv

- `python3.11 -m venv .venv`
- `source .venv/bin/activate`
- `pip install -e .[dev]`
- `pytest *_test.py`

### Using Conda

- `conda create -n .conda_env python=3.11`
- `conda activate .conda_env`
- `pip install -e .[dev]`
- `pytest *_test.py`

### Using uv

- `uv python install 3.10`
- `uv pip install -e '.[dev]'`
- `uv build`
- `uv run pytest`
