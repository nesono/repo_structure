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
