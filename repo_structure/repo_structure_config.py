# pylint: disable=import-error

"""Library functions for repo structure config parsing."""
import copy
import pprint
import re
from dataclasses import dataclass, field
from typing import Dict, List, TextIO, Union, Any, Optional

from ruamel import yaml as YAML
from jsonschema import validate, ValidationError, SchemaError

from .repo_structure_lib import map_dir_to_rel_dir
from .repo_structure_schema import get_json_schema


class StructureRuleError(Exception):
    """Structure rule related error."""


class UseRuleError(Exception):
    """Use_rule related error."""


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
    """Repo Structure configuration class."""

    def __init__(
        self,
        config_file: str,
        param1_is_yaml_string: bool = False,
        schema: Optional[dict[Any, Any]] = None,
        verbose: bool = False,
    ):
        """Create new configuration object.

        Args:
              config_file (str): Path to the configuration file or configuration string.
              param1_is_yaml_string (bool): If true interprets config_file as contents not path.
              schema (dict[Any, Any]): An optional JSON schema file for schema verification.

        Exceptions:
            StructureRuleError: Raised for errors in structure rules.
            UseRuleError: Raised for errors related to the use rule.
            RepoStructureTemplateError: Raised for errors in repository structure templates.
            ConfigurationParseError: Raised for errors during the configuration parsing process.
        """
        if verbose:
            print("Loading configuration")
        if param1_is_yaml_string:
            yaml_dict = _load_repo_structure_yamls(config_file)
        else:
            yaml_dict = _load_repo_structure_yaml(config_file)

        if not yaml_dict:
            raise ConfigurationParseError

        if not schema:
            schema = get_json_schema()

        try:
            validate(instance=yaml_dict, schema=schema)
        except ValidationError as e:
            raise ConfigurationParseError(f"Bad config: {e.message}") from e
        except SchemaError as e:
            raise ConfigurationParseError(f"Bad schema: {e.message}") from e
        if verbose:
            print("Configuration validated successfully")

        if verbose:
            print("Parsing configuration data")

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

        if verbose:
            # Print the parsed configuration pretty
            pprint.pprint(self.config.directory_map, indent=2)
            pprint.pprint(self.config.structure_rules, indent=2)
            print(
                f"Structure rules count: {len(self.config.structure_rules.keys())}, "
                f"Directory map count: {len(self.config.directory_map.keys())}"
            )
            print("Configuration parsed successfully")

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


def _load_repo_structure_yamls(yaml_string: Union[str, TextIO]) -> dict:
    yaml = YAML.YAML(typ="safe")
    return yaml.load(yaml_string)


def _parse_structure_rules(structure_rules_yaml: dict) -> StructureRuleMap:

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

    rules = _build_rules(structure_rules_yaml)
    _validate_use_rule_not_dangling(rules)
    _validate_use_rule_only_recursive(rules)

    return rules


def _build_rules(structure_rules_yaml: dict) -> StructureRuleMap:

    def _parse_directory_structure(
        directory_structure_yaml: dict, structure_rule_list: StructureRuleList
    ) -> None:
        for item in directory_structure_yaml:
            structure_rule_list.append(_parse_entry_to_repo_entry(item))

    rules: StructureRuleMap = {}
    if not structure_rules_yaml:
        return rules

    for rule in structure_rules_yaml:
        structure_rules: StructureRuleList = []
        _parse_directory_structure(structure_rules_yaml[rule], structure_rules)
        rules[rule] = structure_rules
    return rules


def _parse_entry_to_repo_entry(entry: dict) -> RepoEntry:

    if_exists = []
    file = entry["p"]
    if "if_exists" in entry:
        if_exists = entry["if_exists"]

    is_dir = file.endswith("/")
    file = file[0:-1] if is_dir else file

    try:
        compiled_file = re.compile(file)
    except re.error as e:
        raise StructureRuleError(f"Bad pattern {file}, failed to compile: {e}") from e

    result = RepoEntry(
        path=compiled_file,
        is_dir=is_dir,
        is_required=entry["required"] if "required" in entry else True,
        use_rule=entry["use_rule"] if "use_rule" in entry else "",
    )
    for sub_entry in if_exists:
        result.if_exists.append(_parse_entry_to_repo_entry(sub_entry))

    return result


def _expand_template_entry(
    template_yaml: List[dict], expansion_key: str, expansion_var: str
) -> List[dict]:

    def _expand_entry(entry: dict, expansion_key: str, expansion_var: str):
        entry["p"] = entry["p"].replace(f"{{{{{expansion_key}}}}}", expansion_var)
        return entry

    expanded_yaml: List[dict] = []
    for entry in template_yaml:
        entry = _expand_entry(entry, expansion_key, expansion_var)
        if "if_exists" in entry:
            entry["if_exists"] = _expand_template_entry(
                entry["if_exists"], expansion_key, expansion_var
            )
        expanded_yaml.append(entry)
    return expanded_yaml


def _parse_use_template(
    dir_map_yaml: dict, directory: str, templates_yaml: dict, config: Configuration
):
    if "use_template" not in dir_map_yaml:
        return

    def _expand_template(dir_map_yaml, templates_yaml):
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

        expansion_map = _build_expansion_map(dir_map_yaml["parameters"])
        structure_rules_yaml: List[dict] = []
        for i in range(_max_values_length(expansion_map)):
            entries = copy.deepcopy(templates_yaml[dir_map_yaml["use_template"]])
            for expansion_key, expansion_vars in expansion_map.items():
                index = i % len(expansion_vars)
                entries = _expand_template_entry(
                    entries, expansion_key, expansion_vars[index]
                )
            structure_rules_yaml.extend(entries)
        return structure_rules_yaml

    structure_rules_yaml = _expand_template(dir_map_yaml, templates_yaml)

    structure_rule_list = [
        _parse_entry_to_repo_entry(entry) for entry in structure_rules_yaml
    ]

    # fmt: off
    template_rule_name = \
        f"__template_rule_{map_dir_to_rel_dir(directory)}_{dir_map_yaml['use_template']}"
    config.config.structure_rules[template_rule_name] = structure_rule_list
    config.config.directory_map[directory].append(template_rule_name)


def _parse_directory_map(
    directory_map_yaml: dict,
) -> DirectoryMap:

    def _parse_use_rule(rule: dict, dir_map: List[str]) -> None:
        if rule.keys() == {"use_rule"}:
            dir_map.append(rule["use_rule"])

    mapping: DirectoryMap = {}
    for directory, value in directory_map_yaml.items():
        for r in value:
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
