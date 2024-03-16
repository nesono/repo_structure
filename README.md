# Repo Structsure

A tool to control your repository structure.
You can control

* What files and directories are allowed
* Use regexes for specifications
* Map directory structure rules to directories
* Reuse directory structure rules recursively
* Differentiate between required and optional files
* Reuse directory structure rules in directory structure rules

The following example show cases all the supported features

```yaml
structure_rules:
  base_structure:
    required:
      - LICENSE
      - README.md
    optional:
      - .*\.md

  python_package:
    required:
      - setup.py
      - src/:
          - .*\.py
      - tests/:
          -  test_.*\.py
    optional:
      - docs/:
          - use_structure: documentation
    includes:
      - base_structure
    file_dependencies:
      - dependency:
          base: .*\.py
          dependent: test_.*\.py

  documentation:
    required:
      - index.md
    optional:
      - .*\.md

directory_mappings:
  /:
    - use_structure: python_package
  /docs/:
    - use_structure: documentation
    ```