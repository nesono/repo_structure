# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=import-error

"""Library functions for repo structure tool."""
import re
from dataclasses import dataclass
from typing import Dict, List

from ruamel import yaml as YAML


@dataclass
class DirectoryStructure:
    directories: List[re.Pattern]
    files: List[re.Pattern]
    use_structure: Dict[re.Pattern, str]


@dataclass
class FileDependency:
    base: re.Pattern
    dependent: re.Pattern


@dataclass
class StructureRule:
    name: str
    required: DirectoryStructure
    optional: DirectoryStructure
    includes: List[str]
    file_dependencies: Dict[str, FileDependency]


def load_repo_structure_yaml(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        yaml = YAML.YAML(typ="safe")
        result = yaml.load(file)
    return result


def parse_structure_rules(structure_rules: dict) -> Dict[str, StructureRule]:
    rules = {}
    for rule in structure_rules:
        structure = StructureRule(
            name=rule,
            required=parse_directory_structure(
                structure_rules[rule].get("required", {})
            ),
            optional=parse_directory_structure(
                structure_rules[rule].get("optional", {})
            ),
            includes=structure_rules[rule].get("includes", []),
            file_dependencies=parse_file_dependencies(
                structure_rules[rule].get("file_dependencies", {})
            ),
        )
        rules[rule] = structure

    return rules


def parse_directory_structure_recursive(
    result: DirectoryStructure, path: str, cfg: dict
) -> None:
    for item in cfg:
        if isinstance(item, dict):
            for i in item:
                if i == "use_structure":
                    pat = re.compile(path)
                    assert (
                        len(item) == 1
                    ), f"{path}{i} mixing 'use_structure' and files/directories is not supported"
                    assert (
                        path not in result.use_structure
                    ), f'{path}{i} error: "{item[i]}" conflicts with "{result.use_structure[pat]}"'
                    result.use_structure[pat] = item[i]
                else:
                    assert i.endswith(
                        "/"
                    ), f"{i} needs to be suffixed with '/' to be identified as a directory"
                    result.directories.append(re.compile(path + i))
                    parse_directory_structure_recursive(result, path + i, item[i])
        else:
            result.files.append(re.compile(path + item))


def parse_directory_structure(directory_structure: dict) -> DirectoryStructure:
    result = DirectoryStructure(
        directories=[],
        files=[],
        use_structure={},
    )

    parse_directory_structure_recursive(result, "", directory_structure)
    return result


def parse_file_dependencies(file_dependencies: dict) -> Dict[str, FileDependency]:
    result: Dict[str, FileDependency] = {}
    for dep in file_dependencies:
        for name in dep:
            assert len(dep[name]) == 2, f"{name} can only have one base spec"
            assert "base" in dep[name], f'{name} needs to contain "base" field'
            assert (
                "dependent" in dep[name]
            ), f'{name} needs to contain "dependent" field'
            result[name] = FileDependency(
                base=re.compile(dep[name]["base"]),
                dependent=re.compile(dep[name]["dependent"]),
            )
    return result
