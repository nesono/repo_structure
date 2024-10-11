# pylint: disable=import-error

"""Library functions for repo structure config parsing."""
import re
from dataclasses import dataclass, field
from typing import Dict, List, TextIO, Union

from ruamel import yaml as YAML

from repo_structure_lib import map_dir_to_rel_dir


class StructureRuleError(Exception):
    """Structure rule related error."""


class UseRuleError(Exception):
    """Use_rule related error."""


class DirectoryStructureError(Exception):
    """Directory structure related error."""


class RepoStructureTemplateError(Exception):
    """Repo structure template related error."""


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
        # Template parsing is expanded in-place and added as structure rules to the directory_map
        _parse_templates_to_configuration(
            yaml_dict.get("templates", {}),
            yaml_dict.get("directory_map", {}),
            self,
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


def _build_expansion_map(dir_map_yaml: dict) -> Dict[str, List[str]]:
    expansion_map = {}
    for key in dir_map_yaml.keys():
        if key != "use_template":
            expansion_map[key] = dir_map_yaml[key]
    return expansion_map


def _max_values_length(expansion_map: Dict[str, List[str]]) -> int:
    max_length = 0
    for _, values in expansion_map.items():
        max_length = max(max_length, len(values))
    return max_length


def _expand_entry(entry: Union[dict, str], expansion_key: str, expansion_var: str):
    if isinstance(entry, dict):
        entry_key = next(iter(entry.keys()))
        return entry_key.replace(f"{{{{{expansion_key}}}}}", expansion_var)

    if isinstance(entry, str):
        return entry.replace(f"{{{{{expansion_key}}}}}", expansion_var)

    raise RepoStructureTemplateError(
        "only instances 'dict' and 'str' are" f" allowed, but found '{type(entry)}'"
    )


def _parse_use_template(
    dir_map_yaml: dict, directory: str, templates_yaml: dict, config: Configuration
):
    if "use_template" not in dir_map_yaml:
        return

    template_name = dir_map_yaml["use_template"]
    expansion_map = _build_expansion_map(dir_map_yaml)
    template_entries = templates_yaml[template_name]

    structure_rule_list: StructureRuleList = []
    for i in range(_max_values_length(expansion_map)):
        for entry in template_entries:
            for expansion_key, expansion_vars in expansion_map.items():
                index = i % len(expansion_vars)
                entry = _expand_entry(entry, expansion_key, expansion_vars[index])
            structure_rule_list.append(_parse_entry_to_repo_entry(entry))

    template_rule_name = (
        f"__template_rule_{map_dir_to_rel_dir(directory)}_{template_name}"
    )
    config.config.structure_rules[template_rule_name] = structure_rule_list
    config.config.directory_map[directory].append(template_rule_name)


def _parse_directory_map(
    directory_map_yaml: dict,
) -> DirectoryMap:

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

    def _parse_use_rule(rule: dict, dir_map: List[str]) -> None:
        if rule.keys() == {"use_rule"}:
            dir_map.append(rule["use_rule"])

    mapping: DirectoryMap = {}
    for directory, value in directory_map_yaml.items():
        _ensure_start_and_end_slashes(directory)
        for r in value:
            _validate_directory_map_keys(r)
            if mapping.get(directory) is None:
                mapping[directory] = []
            _parse_use_rule(r, mapping[directory])

    return mapping


def _parse_templates_to_configuration(
    templates_yaml: dict, directory_map_yaml: dict, config: Configuration
) -> None:
    for directory, value in directory_map_yaml.items():
        for use_map in value:
            _parse_use_template(use_map, directory, templates_yaml, config)
