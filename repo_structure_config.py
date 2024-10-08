# pylint: disable=import-error

"""Library functions for repo structure config parsing."""
import re
from dataclasses import dataclass, field
from typing import Dict, List, TextIO

from ruamel import yaml as YAML


class StructureRuleError(Exception):
    """Structure rule related error."""


class UseRuleError(Exception):
    """Use_rule related error."""


class DirectoryStructureError(Exception):
    """Directory structure related error."""


@dataclass
class RepoEntry:
    """Wrapper for entries in the directory structure, that store the path
    as a string together with the entry type."""

    path: re.Pattern
    is_dir: bool
    is_required: bool
    use_rule: str = ""
    if_exists: List["RepoEntry"] = field(default_factory=list)
    count: int = 0


DirectoryMap = Dict[str, List[str]]
StructureRuleList = List[RepoEntry]
StructureRuleMap = Dict[str, StructureRuleList]


@dataclass
class ConfigurationData:
    """Stores configuration data."""

    structure_rules: StructureRuleMap = field(default_factory=dict)
    directory_map: DirectoryMap = field(default_factory=dict)


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
            directory_map=_parse_directory_map(yaml_dict.get("directory_map", {})),
        )
        self._validate_directory_map_use_rules()

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

            self.config.directory_map["/"].insert(0, config_file)

    def _validate_directory_map_use_rules(self):
        existing_rules = self.config.structure_rules.keys()
        for directory, rule in self.config.directory_map.items():
            for r in rule:
                if r not in existing_rules:
                    raise UseRuleError(
                        f"Directory mapping '{directory}' uses non-existing rule '{r}'"
                    )

    @property
    def structure_rules(self) -> StructureRuleMap:
        """Property for structure rules."""
        return self.config.structure_rules

    @property
    def directory_map(self) -> DirectoryMap:
        """Property for directory mappings."""
        return self.config.directory_map


def _load_repo_structure_yaml(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        return _load_repo_structure_yamls(file)


def _load_repo_structure_yamls(yaml_string: str | TextIO) -> dict:
    yaml = YAML.YAML(typ="safe")
    result = yaml.load(yaml_string)
    return result


def _parse_structure_rules(structure_rules_yaml: dict) -> StructureRuleMap:
    _validate_yaml_dict(structure_rules_yaml)

    rules = _build_rules(structure_rules_yaml)
    _validate_use_rule_not_dangling(rules)
    _validate_use_rule_only_recursive(rules)

    return rules


def _build_rules(structure_rules_yaml: dict) -> StructureRuleMap:
    rules: StructureRuleMap = {}
    if not structure_rules_yaml:
        return rules

    for rule in structure_rules_yaml:
        structure_rules: StructureRuleList = []
        _parse_directory_structure(structure_rules_yaml[rule], structure_rules)
        rules[rule] = structure_rules
    return rules


def _parse_directory_structure(
    directory_structure_yaml: dict, structure_rule_list: StructureRuleList
) -> None:
    # if directory_structure is empty dict, return
    if not directory_structure_yaml:
        return
    for item in directory_structure_yaml:
        structure_rule_list.append(_parse_entry_to_repo_entry(item))


def _validate_structure_rule_entry_keys(entry: dict, file: str) -> None:
    allowed_keys = {file, "use_rule", "if_exists"}
    if not entry.keys() <= allowed_keys:
        raise StructureRuleError(
            f"only 'use_rule' and file name is allowed"
            f"as an entry key, but contains extra keys '{entry.keys() - allowed_keys}'"
        )


def _parse_entry_to_repo_entry(entry: dict) -> RepoEntry:
    mode = True
    use_rule = ""
    if_exists = []
    if isinstance(entry, dict):
        file = next(iter(entry.keys()))
        _validate_structure_rule_entry_keys(entry, file)
        if entry[file] not in [None, "required", "optional"]:
            raise StructureRuleError(
                f"mode must be either 'required' or 'optional'"
                f"but is '{entry[file]}'"
            )
        mode = entry[file] != "optional"
        if "use_rule" in entry:
            use_rule = entry["use_rule"]
        if "if_exists" in entry:
            if_exists = entry["if_exists"]
    else:
        file = entry

    is_dir = file.endswith("/")
    file = file[0:-1] if is_dir else file

    result = RepoEntry(
        path=re.compile(file),
        is_dir=is_dir,
        is_required=mode,
        use_rule=use_rule,
    )
    for e in if_exists:
        result.if_exists.append(_parse_entry_to_repo_entry(e))

    return result


def _validate_yaml_dict(yaml_dict: dict) -> None:
    if not isinstance(yaml_dict, dict):
        raise StructureRuleError(
            f"Structure rules must be a dictionary, but is '{type(yaml_dict)}'"
        )
    for key in yaml_dict:
        if not isinstance(yaml_dict[key], list):
            raise StructureRuleError(
                f"Structure rules must be a dictionary of lists, but is '{type(yaml_dict[key])}'"
            )


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


def _handle_use_rule(rule: dict, mapping: DirectoryMap, directory: str):
    if rule.keys() == {"use_rule"}:
        mapping[directory].append(rule["use_rule"])


# def _handle_use_template(rule: dict, mapping: DirectoryMap, directory: str):
#     if "use_template" in rule.keys():
#         template = rule["use_template"]
#         print(f"found template usage {template} in {directory}")


def _parse_directory_map(directory_map: dict) -> DirectoryMap:
    mapping: DirectoryMap = {}
    for directory, value in directory_map.items():
        _ensure_start_and_end_slashes(directory)
        for r in value:
            _validate_directory_map_keys(r)
            if mapping.get(directory) is None:
                mapping[directory] = []
            _handle_use_rule(r, mapping, directory)
            # _handle_use_template(r, mapping, directory)

    return mapping


def _ensure_start_and_end_slashes(directory):
    if not (directory.startswith("/") and directory.endswith("/")):
        raise DirectoryStructureError(
            f"Directory mapping must start and end with '/', but is '{directory}'"
        )


def _validate_directory_map_keys(r):
    if r.keys() == {"use_rule"}:
        return
    if "use_template" not in r.keys():
        raise ValueError(
            "Only 'use_rule' or 'use_template' are allowed "
            f"in directory mappings, but is '{r.keys()}'"
        )
