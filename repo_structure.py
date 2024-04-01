import ruamel.yaml as YAML
from dataclasses import dataclass
from typing import List, Dict
import re


@dataclass
class DirectoryStructure:
    directories: List[re.Pattern]
    files: List[re.Pattern]
    references: Dict[re.Pattern, str]

@dataclass
class FileDependency:
    base: re.Pattern
    dependent: re.Pattern


@dataclass
class StructureRule:
    name: str
    required: List[DirectoryStructure]
    optional: List[DirectoryStructure]
    includes: List[DirectoryStructure]
    file_dependencies: Dict[str, FileDependency]


def load_repo_structure_yaml(filename: str) -> dict:
    with open(filename, 'r') as file:
        yaml = YAML.YAML(typ='safe')
        result = yaml.load(file)
    return result


def parse_structure_rules(structure_rules: dict) -> List[StructureRule]:
    rules = []
    for rule in structure_rules:
        structure = StructureRule(
            name=rule,
            required=structure_rules.get("required", []),
            optional=structure_rules.get("optional", []),
            includes=structure_rules.get("includes", []),
            file_dependencies=structure_rules.get("file_dependencies", {})
        )
        rules.append(structure)

    return rules


def parse_directory_structure_recursive(result: DirectoryStructure, path: str, cfg: dict) -> None:
    for item in cfg:
        if isinstance(item, dict):
            for i in item:
                if i == "use_structure":
                    assert len(item) == 1, f"{path}{i} mixing 'use_structure' and files/directories is not supported"
                    assert path not in result.references, f"{path}{i} only a single reference is allowed"
                    result.references[path] = item[i]
                else:
                    assert i.endswith("/"), f"{i} needs to be suffixed with '/' to be identified as a directory"
                    result.directories.append(re.compile(path + i))
                    parse_directory_structure_recursive(result, path + i, item[i])
        elif item.endswith("/"):
            raise NotImplementedError("plain directory not implemented")
        else:
            result.files.append(re.compile(path + item))


def parse_directory_structure(directory_structure: dict) -> DirectoryStructure:
    result = DirectoryStructure(
        directories=[],
        files=[],
        references={},
    )

    parse_directory_structure_recursive(result, "", directory_structure)
    return result
