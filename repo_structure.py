# pylint: disable=missing-function-docstring
# pylint: disable=import-error

"""Library functions for repo structure tool."""
import re
from dataclasses import dataclass, field
from typing import Dict, Final, List

import os
from io import TextIOWrapper
from ruamel import yaml as YAML

# An entry here is an entry for files / directories.
# The allowed keys matches the supported dict keys for parsing.
ALLOWED_ENTRY_KEYS: Final = [
    "name",
    "mode",
    "depends",
    "depends_path",
    "use_rule",
    "files",
    "dirs",
]


@dataclass
class DirectoryStructure:
    """Storing directory structure rules.

    Storing directories and files separately helps for parsing.
    All directories and files are stored expanded and not in a
    tree to facilitate parsing.
    """

    directories: List[re.Pattern] = field(default_factory=list)
    files: List[re.Pattern] = field(default_factory=list)
    use_rule: Dict[re.Pattern, str] = field(default_factory=dict)


@dataclass
class FileDependency:
    """Storing file dependency specifications.

    File dependencies are dependencies where two files share a
    certain portion of the filename together, e.g. test and
    implementation files"""

    depends: re.Pattern


@dataclass
class StructureRule:
    """Storing structure rule.

    Compound instance for structure rules, e.g. cpp_source,
    python_package, etc."""

    name: str = field(default_factory=str)
    required: DirectoryStructure = field(default_factory=DirectoryStructure)
    optional: DirectoryStructure = field(default_factory=DirectoryStructure)
    dependencies: Dict[re.Pattern, FileDependency] = field(default_factory=dict)


@dataclass
class DirectoryMapping:
    """Stores mapping of directory names to Structure Rule names."""
    map: Dict[re.Pattern, str] = field(default_factory=dict)


def load_repo_structure_yaml(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        return load_repo_structure_yamls(file)


def load_repo_structure_yamls(yaml_string: str | TextIOWrapper) -> dict:
    yaml = YAML.YAML(typ="safe")
    result = yaml.load(yaml_string)
    return result


def _build_rules(structure_rules: dict) -> Dict[str, StructureRule]:
    rules: Dict[str, StructureRule] = {}
    if not structure_rules:
        return rules

    for rule in structure_rules:
        structure = StructureRule()
        parse_directory_structure(structure_rules[rule], structure)
        rules[rule] = structure
    return rules


def _validate_use_rule_not_dangling(rules: Dict[str, StructureRule]) -> None:
    all_use_rule: List[str] = []
    for use_rule_list in [r.required.use_rule.values() for r in rules.values()]:
        if use_rule_list:
            all_use_rule.extend(use_rule_list)

    for use_rule_list in [r.optional.use_rule.values() for r in rules.values()]:
        if use_rule_list:
            all_use_rule.extend(use_rule_list)

    for use_rule in all_use_rule:
        if use_rule not in rules.keys():
            raise ValueError(f"use_rule rule {use_rule} not found in 'structure_rules'")


def _validate_use_rule_not_mixed(rules: Dict[str, StructureRule]) -> None:
    for rule in rules.values():
        for k in rule.required.use_rule.keys():
            if (
                    k in rule.required.files
                    or k in rule.required.directories
                    or rule.optional.files
                    or rule.optional.directories
            ):
                raise ValueError(
                    f"do not mix use_rule with files or directories. Violating key: {k}"
                )


def parse_structure_rules(structure_rules: dict) -> Dict[str, StructureRule]:
    """
    This function parses the input rules and returns a dictionary,
    where keys are rule names and values are StructureRule instances.
    It validates that all included rules are valid.
    """
    rules = _build_rules(structure_rules)
    _validate_use_rule_not_dangling(rules)
    _validate_use_rule_not_mixed(rules)

    # We do not validate dependencies towards being allowed, since that
    # would require us to check if the 'depends' pattern is fully enclosed
    # in any file name pattern

    return rules


def _validate_path_entry(entry: dict) -> None:
    if "name" not in entry:
        raise ValueError(f"name not defined in entry with key '{entry}'")
    if "mode" in entry and entry["mode"] not in ["required", "optional"]:
        raise ValueError(
            f"mode must be either 'required' or 'optional' but is '{entry['mode']}'"
        )
    for k in entry.keys():
        if k not in ALLOWED_ENTRY_KEYS:
            raise ValueError(f"Unsupported key '{k}' in entry {entry}")


def _get_required_or_optional(entry: dict) -> str:
    if "mode" in entry:
        return entry["mode"]
    return "required"


def _parse_file_or_directory(
        entry: dict, is_dir: bool, path: str, structure_rule: StructureRule
):
    _validate_path_entry(entry)

    local_path = os.path.join(path, entry["name"])

    mode = _get_required_or_optional(entry)
    add_to = structure_rule.required if mode == "required" else structure_rule.optional

    if is_dir:
        add_to.directories.append(re.compile(local_path))
    else:
        add_to.files.append(re.compile(local_path))

    if "depends" in entry:
        if "depends_path" in entry:
            depends = os.path.join(entry["depends_path"], entry["depends"])
        else:
            depends = entry["depends"]

        structure_rule.dependencies[re.compile(local_path)] = FileDependency(
            depends=re.compile(depends)
        )
    elif "depends_path" in entry:
        raise ValueError(f"depends_path without depends spec in {entry}")

    if "use_rule" in entry:
        add_to.use_rule[re.compile(local_path)] = entry["use_rule"]

    return local_path


def _parse_directory_structure_recursive(
        path: str, cfg: dict, structure_rule: StructureRule
) -> None:
    for d in cfg.get("dirs", []):
        local_path = _parse_file_or_directory(d, True, path, structure_rule)
        _parse_directory_structure_recursive(local_path, d, structure_rule)
    for f in cfg.get("files", []):
        _parse_file_or_directory(f, False, path, structure_rule)


def parse_directory_structure(
        directory_structure: dict, structure_rule: StructureRule
) -> None:
    """"Parse a full directory structure (recursively)."""
    _parse_directory_structure_recursive("", directory_structure, structure_rule)


def parse_directory_mappings(directory_mappings: dict) -> DirectoryMapping:
    mapping = DirectoryMapping()
    for pattern, rule_name in directory_mappings.items():
        mapping.map[re.compile(pattern)] = rule_name
    return mapping
