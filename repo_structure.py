# pylint: disable=missing-function-docstring
# pylint: disable=import-error

"""Library functions for repo structure tool."""
import re
from dataclasses import dataclass
from typing import Dict, List

from ruamel import yaml as YAML


@dataclass
class DirectoryStructure:
    """Storing directory structure rules.

    Storing directories and files separately helps for parsing.
    All directories and files are stored expanded and not in a
    tree to facilitate parsing.
    """

    directories: List[re.Pattern]
    files: List[re.Pattern]
    use_rule: Dict[re.Pattern, str]


@dataclass
class FileDependency:
    """Storing file dependency specifications.

    File dependencies are dependencies where two files share a
    certain portion of the filename together, e.g. test and
    implementation files"""

    base: re.Pattern
    dependent: re.Pattern


@dataclass
class StructureRule:
    """Storing structure rule.

    Compound instance for structure rules, e.g. cpp_source,
    python_package, etc."""

    name: str
    required: DirectoryStructure
    optional: DirectoryStructure
    file_dependencies: Dict[str, FileDependency]


def load_repo_structure_yaml(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        yaml = YAML.YAML(typ="safe")
        result = yaml.load(file)
    return result


def load_repo_structure_yamls(yaml_string: str) -> dict:
    yaml = YAML.YAML(typ="safe")
    result = yaml.load(yaml_string)
    return result


def _build_rules(structure_rules: dict) -> Dict[str, StructureRule]:
    rules: Dict[str, StructureRule] = {}
    if not structure_rules:
        return rules

    for rule in structure_rules:
        print(rule)
        structure = StructureRule(
            name=rule,
            required=parse_directory_structure(
                structure_rules[rule].get("required", {})
            ),
            optional=parse_directory_structure(
                structure_rules[rule].get("optional", {})
            ),
            file_dependencies=parse_file_dependencies(
                structure_rules[rule].get("file_dependencies", {})
            ),
        )
        rules[rule] = structure
    return rules


def _validate_use_rule(rules: Dict[str, StructureRule]):
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


def parse_structure_rules(structure_rules: dict) -> Dict[str, StructureRule]:
    """
    This function parses the input rules and returns a dictionary,
    where keys are rule names and values are StructureRule instances.
    It validates that all included rules are valid.
    """
    rules = _build_rules(structure_rules)
    _validate_use_rule(rules)
    # validate that the file_dependencies match any of the
    # allowed files (both required and optional)
    return rules


def _parse_directory_structure_recursive(
    result: DirectoryStructure, path: str, cfg: dict, parent_len: int = 0
) -> None:
    for item in cfg:
        if isinstance(item, dict):
            for i in item:
                if i == "use_rule":
                    pat = re.compile(path)
                    if parent_len != 1:
                        raise ValueError(
                            f"{path}{i} mixing 'use_rule' and files/directories not supported"
                        )
                    if pat in result.use_rule:
                        raise ValueError(
                            f'{path}{i}: "{item[i]}" conflicts with "{result.use_rule[pat]}"'
                        )
                    result.use_rule[pat] = item[i]
                else:
                    if not i.endswith("/"):
                        raise ValueError(
                            f"{i} needs to be suffixed with '/' to be identified as a directory"
                        )
                    result.directories.append(re.compile(path + i))
                    _parse_directory_structure_recursive(
                        result, path + i, item[i], len(item[i])
                    )
        else:
            result.files.append(re.compile(path + item))


def parse_directory_structure(directory_structure: dict) -> DirectoryStructure:
    result = DirectoryStructure(
        directories=[],
        files=[],
        use_rule={},
    )

    _parse_directory_structure_recursive(result, "", directory_structure)
    return result


def parse_file_dependencies(file_dependencies: dict) -> Dict[str, FileDependency]:
    result: Dict[str, FileDependency] = {}
    for dep in file_dependencies:
        for name in dep:
            if len(dep[name]) != 2:
                raise ValueError(f"'{name}' must have two elements")
            if "base" not in dep[name]:
                raise ValueError(f"'{name}' must contain a base")
            if "dependent" not in dep[name]:
                raise ValueError(f"'{name}' must contain a dependent")

            result[name] = FileDependency(
                base=re.compile(dep[name]["base"]),
                dependent=re.compile(dep[name]["dependent"]),
            )
    return result
