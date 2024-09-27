# pylint: disable=import-error

"""Library functions for repo structure config parsing."""
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Final, List, TextIO

from ruamel import yaml as YAML


# An entry here is an entry for files / directories.
# The allowed keys matches the supported dict keys for parsing.
ALLOWED_ENTRY_KEYS: Final = [
    "name",
    "mode",
    "depends",
    "use_rule",
    "files",
    "dirs",
]


class UseRuleError(Exception):
    """Use_rule related error."""


@dataclass
class RepoEntry:
    """Wrapper for entries in the directory structure, that store the path
    as a string together with the entry type."""

    path: re.Pattern
    is_dir: bool
    is_required: bool
    use_rule: str = ""
    depends: re.Pattern = re.compile(r"")
    count: int = 0


DirectoryMap = Dict[str, List[str]]
StructureRuleList = List[RepoEntry]
StructureRuleMap = Dict[str, StructureRuleList]


@dataclass
class ConfigurationData:
    """Stores configuration data."""

    structure_rules: StructureRuleMap = field(default_factory=dict)
    directory_mappings: DirectoryMap = field(default_factory=dict)


class ConfigurationParseError(Exception):
    """Thrown when configuration could not be parsed."""


class Configuration:
    """Repo Structure configuration."""

    def __init__(self, config_file: str, param1_is_yaml_string: bool = False):
        if param1_is_yaml_string:
            yaml_dict = _load_repo_structure_yamls(config_file)
        else:
            yaml_dict = _load_repo_structure_yaml(config_file)

        if not yaml_dict:
            raise ConfigurationParseError

        self.config = ConfigurationData(
            structure_rules=_parse_structure_rules(
                yaml_dict.get("structure_rules", {})
            ),
            directory_mappings=_parse_directory_mappings(
                yaml_dict.get("directory_mappings", {})
            ),
        )

        if not param1_is_yaml_string:
            if config_file in self.config.structure_rules:
                raise ConfigurationParseError(
                    f"Conflicting Structure rule for {config_file}"
                    "- do not add the config manually."
                )

            # add the config file to the config
            self.config.structure_rules[config_file] = [
                RepoEntry(
                    path=re.compile(config_file),
                    is_dir=False,
                    is_required=True,
                )
            ]

            self.config.directory_mappings["/"].insert(0, config_file)

    @property
    def structure_rules(self) -> StructureRuleMap:
        """Property for structure rules."""
        return self.config.structure_rules

    @property
    def directory_mappings(self) -> DirectoryMap:
        """Property for directory mappings."""
        return self.config.directory_mappings


def _load_repo_structure_yaml(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        return _load_repo_structure_yamls(file)


def _load_repo_structure_yamls(yaml_string: str | TextIO) -> dict:
    yaml = YAML.YAML(typ="safe")
    result = yaml.load(yaml_string)
    return result


def _build_rules(structure_rules_yaml: dict) -> StructureRuleMap:
    rules: StructureRuleMap = {}
    if not structure_rules_yaml:
        return rules

    for rule in structure_rules_yaml:
        structure_rules: StructureRuleList = []
        _parse_directory_structure(structure_rules_yaml[rule], structure_rules)
        rules[rule] = structure_rules
    return rules


def _validate_use_rule_not_dangling(rules: StructureRuleMap) -> None:
    for rule_key in rules.keys():
        for entry in rules[rule_key]:
            if entry.use_rule and entry.use_rule not in rules:
                raise UseRuleError(
                    f"use_rule '{entry.use_rule}' in entry '{entry.path.pattern}'"
                    "is not a valid rule key"
                )


def _validate_use_rule_only_recursive(rules: StructureRuleMap) -> None:
    for rule_key in rules.keys():
        for entry in rules[rule_key]:
            if entry.use_rule and entry.use_rule != rule_key:
                raise UseRuleError(
                    f"use_rule '{entry.use_rule}' in entry '{entry.path.pattern}'"
                    "is not recursive"
                )


def _parse_structure_rules(structure_rules_yaml: dict) -> StructureRuleMap:
    rules = _build_rules(structure_rules_yaml)
    _validate_use_rule_not_dangling(rules)
    _validate_use_rule_only_recursive(rules)

    # Note: We do not validate dependencies towards being allowed, since that
    # would require us to check if the 'depends' pattern is fully enclosed
    # in any file name pattern, which is non-trivial and seems not worth
    # the hassle.

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


def _parse_use_rule(entry: dict, local_path: str) -> str:
    if "use_rule" in entry:
        if "dirs" in entry:
            raise UseRuleError(f"Unsupported dirs next to use_rule in {local_path}")
        if "files" in entry:
            raise UseRuleError(f"Unsupported files next to use_rule in {local_path}")
        return entry["use_rule"]
    return ""


def _parse_file_or_directory(
    input_yaml: dict, is_dir: bool, path: str, structure_rule_list: StructureRuleList
) -> str:
    _validate_path_entry(input_yaml)

    local_path = os.path.join(path, input_yaml["name"])

    mode = _get_required_or_optional(input_yaml)
    use_rule = _parse_use_rule(input_yaml, local_path)
    depends = re.compile(input_yaml.get("depends", ""))

    structure_rule_list.append(
        RepoEntry(
            path=re.compile(local_path),
            is_dir=is_dir,
            is_required=mode == "required",
            use_rule=use_rule,
            depends=depends,
        )
    )

    return local_path


def _parse_directory_structure_recursive(
    path: str, directory_structure_yaml: dict, structure_rule_list: StructureRuleList
) -> None:
    for d in directory_structure_yaml.get("dirs", []):
        local_path = _parse_file_or_directory(d, True, path, structure_rule_list)
        _parse_directory_structure_recursive(local_path, d, structure_rule_list)
    for f in directory_structure_yaml.get("files", []):
        _parse_file_or_directory(f, False, path, structure_rule_list)


def _parse_directory_structure(
    directory_structure_yaml: dict, structure_rule_list: StructureRuleList
) -> None:
    # if directory_structure is empty dict, return
    if not directory_structure_yaml:
        return
    _parse_directory_structure_recursive(
        "", directory_structure_yaml, structure_rule_list
    )


def _parse_directory_mappings(directory_mappings: dict) -> DirectoryMap:
    mapping: DirectoryMap = {}
    for directory, rules in directory_mappings.items():
        for r in rules:
            if r.keys() != {"use_rule"}:
                raise ValueError(
                    f"Only a 'use_rule' is allowed in directory mappings, but is '{r.keys()}'"
                )
            if mapping.get(directory) is None:
                mapping[directory] = []
            mapping[directory].append(r["use_rule"])

    return mapping
