# pylint: disable=import-error

"""Library functions for repo structure config parsing."""
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from io import TextIOWrapper
from typing import Dict, Final, List

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


class EntryType(Enum):
    """Type of the directory entry, to allow for put all wrappers in a list."""

    FILE = "file"
    DIR = "dir"


class ContentRequirement(Enum):
    """Requirement mode for the directory entry."""

    OPTIONAL = "optional"
    REQUIRED = "required"


@dataclass
class DirectoryEntryWrapper:
    """Wrapper for entries in the directory structure, that store the path
    as a string together with the entry type."""

    path: re.Pattern
    entry_type: EntryType
    content_requirement: ContentRequirement
    use_rule: str = ""
    depends: re.Pattern = re.compile(r"")


@dataclass
class DirectoryStructure:
    """Storing directory structure rules.

    Storing directories and files separately helps for parsing.
    All directories and files are stored expanded and not in a
    tree to facilitate parsing.
    """

    directories: List[re.Pattern] = field(default_factory=list)
    files: List[re.Pattern] = field(default_factory=list)


@dataclass
class StructureRule:
    """Storing structure rule.

    Compound instance for structure rules, e.g. cpp_source,
    python_package, etc."""

    name: str = field(default_factory=str)
    entries: List[DirectoryEntryWrapper] = field(default_factory=list)

    required: DirectoryStructure = field(default_factory=DirectoryStructure)
    optional: DirectoryStructure = field(default_factory=DirectoryStructure)
    use_rule: Dict[re.Pattern, str] = field(default_factory=dict)
    dependencies: Dict[re.Pattern, re.Pattern] = field(default_factory=dict)


@dataclass
class ConfigurationData:
    """Stores configuration data."""

    structure_rules: Dict[str, StructureRule] = field(default_factory=dict)
    directory_mappings: Dict[str, List[str]] = field(default_factory=dict)


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
                    f"Conflicting Structure rule for {config_file}. No need to add the config to the configuration file."
                )

            # add the config file to the config
            self.config.structure_rules[config_file] = StructureRule(
                name=config_file,
                entries=[
                    DirectoryEntryWrapper(
                        re.compile(config_file),
                        EntryType.FILE,
                        ContentRequirement.REQUIRED,
                    )
                ],
            )
            self.config.directory_mappings["/"].append(config_file)

    @property
    def structure_rules(self) -> Dict[str, StructureRule]:
        """Property for structure rules."""
        return self.config.structure_rules

    @property
    def directory_mappings(self) -> Dict[str, List[str]]:
        """Property for directory mappings."""
        return self.config.directory_mappings


def _load_repo_structure_yaml(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        return _load_repo_structure_yamls(file)


def _load_repo_structure_yamls(yaml_string: str | TextIOWrapper) -> dict:
    yaml = YAML.YAML(typ="safe")
    result = yaml.load(yaml_string)
    return result


def _build_rules(structure_rules: dict) -> Dict[str, StructureRule]:
    rules: Dict[str, StructureRule] = {}
    if not structure_rules:
        return rules

    for rule in structure_rules:
        structure = StructureRule()
        structure.name = rule
        _parse_directory_structure(structure_rules[rule], structure)
        rules[rule] = structure
    return rules


def _validate_use_rule_not_dangling(rules: Dict[str, StructureRule]) -> None:
    for use_rule in rules.keys():
        for entry in rules[use_rule].entries:
            if entry.use_rule and entry.use_rule != use_rule:
                raise ValueError(
                    f"use_rule rule {use_rule} not found in 'structure_rules'"
                )


def _parse_structure_rules(structure_rules: dict) -> Dict[str, StructureRule]:
    rules = _build_rules(structure_rules)
    _validate_use_rule_not_dangling(rules)

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


class UseRuleError(Exception):
    """Use_rule related error."""


def _parse_use_rule(entry: dict, local_path: str) -> str:
    if "use_rule" in entry:
        if "dirs" in entry:
            raise UseRuleError(f"Unsupported dirs next to use_rule in {local_path}")
        if "files" in entry:
            raise UseRuleError(f"Unsupported files next to use_rule in {local_path}")
        return entry["use_rule"]
    return ""


def _parse_file_or_directory(
    entry: dict, is_dir: bool, path: str, structure_rule: StructureRule
) -> str:
    _validate_path_entry(entry)

    local_path = os.path.join(path, entry["name"])

    mode = _get_required_or_optional(entry)
    use_rule = _parse_use_rule(entry, local_path)
    if use_rule and structure_rule.name != use_rule:
        raise UseRuleError(
            f'Non recursive use_rule for "{structure_rule.name}" '
            f"-> \"{entry['use_rule']}\" - path {local_path}"
        )
    depends = re.compile(entry.get("depends", ""))

    structure_rule.entries.append(
        DirectoryEntryWrapper(
            re.compile(local_path),
            EntryType.DIR if is_dir else EntryType.FILE,
            (
                ContentRequirement.OPTIONAL
                if mode == "optional"
                else ContentRequirement.REQUIRED
            ),
            use_rule,
            depends,
        )
    )

    return local_path


def _parse_directory_structure_recursive(
    path: str, cfg: dict, structure_rule: StructureRule
) -> None:
    assert "dirs" in cfg or "files" in cfg or "use_rule" in cfg, (
        f"Neither 'dirs', nor 'files', nor 'use_rule' found during "
        f"parsing in structure rule: {structure_rule.name} "
        f"in path: {path}"
    )
    for d in cfg.get("dirs", []):
        local_path = _parse_file_or_directory(d, True, path, structure_rule)
        if "dirs" in d or "files" in d or "use_rule" in d:
            _parse_directory_structure_recursive(local_path, d, structure_rule)
    for f in cfg.get("files", []):
        _parse_file_or_directory(f, False, path, structure_rule)


def _parse_directory_structure(
    directory_structure: dict, structure_rule: StructureRule
) -> None:
    # if directory_structure is empty dict, return
    if not directory_structure:
        return
    _parse_directory_structure_recursive("", directory_structure, structure_rule)


def _parse_directory_mappings(directory_mappings: dict) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
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
