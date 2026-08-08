"""Library functions for repo structure config parsing."""

import copy
import logging
import re
from typing import NamedTuple, TextIO, Any

from ruamel import yaml as YAML
from jsonschema import validate, ValidationError, SchemaError

from .config_merge import build_config_tree
from .errors import ConfigurationParseError, StructureRuleError, TemplateError
from .models import (
    ConfigurationData,
    InheritSpec,
    ParsedDocument,
    RepoEntry,
    DirectoryMap,
    StructureRuleList,
    StructureRuleMap,
    BUILTIN_DIRECTORY_RULES,
)
from .paths import map_dir_to_rel_dir, relative_to_root
from .schema import get_json_schema

_LOGGER = logging.getLogger(__name__)


def _set_verbosity(verbose: bool) -> None:
    """Raise the package logger to DEBUG when a caller asks for verbosity."""
    if verbose:
        logging.getLogger(__package__).setLevel(logging.DEBUG)


class Configuration:
    """Repo Structure configuration class.

    Build one with :meth:`from_file` or :meth:`from_yaml_string`; the
    constructor takes the already-merged configuration data.
    """

    @classmethod
    def from_file(
        cls,
        path: str,
        *,
        schema: dict[Any, Any] | None = None,
        verbose: bool = False,
    ) -> "Configuration":
        """Build a Configuration from a YAML file on disk.

        Args:
            path: Filesystem path to the YAML configuration file.
            schema: Optional JSON schema to validate the YAML against.
            verbose: Emit DEBUG-level diagnostic messages during parsing.

        Exceptions:
            StructureRuleError: Raised for errors in structure rules.
            TemplateError: Raised for errors in repository structure templates.
            ConfigurationParseError: Raised for errors during configuration parsing.
        """
        _set_verbosity(verbose)
        return cls(build_config_tree(path, lambda p: load_document(p, schema)))

    @classmethod
    def from_yaml_string(
        cls,
        yaml_string: str,
        *,
        schema: dict[Any, Any] | None = None,
        verbose: bool = False,
    ) -> "Configuration":
        """Build a Configuration directly from a YAML string.

        Args:
            yaml_string: Raw YAML configuration text.
            schema: Optional JSON schema to validate the YAML against.
            verbose: Emit DEBUG-level diagnostic messages during parsing.

        Exceptions:
            StructureRuleError: Raised for errors in structure rules.
            TemplateError: Raised for errors in repository structure templates.
            ConfigurationParseError: Raised for errors during configuration parsing.
        """
        _set_verbosity(verbose)
        return cls(_build_from_yaml_string(yaml_string, schema))

    def __init__(self, config: ConfigurationData):
        """Wrap already-merged configuration data.

        Args:
            config: The flattened result of loading every participating
                configuration file -- see :func:`config_merge.build_config_tree`.
        """
        self.config = config

        self._validate_cross_references()

        _LOGGER.debug(
            "Structure rules count: %d, Directory map count: %d",
            len(self.config.structure_rules),
            len(self.config.directory_map),
        )
        _LOGGER.debug("Configuration parsed successfully")

    def _validate_cross_references(self):
        """Ensure every rule referenced by the directory map exists."""
        existing_rules = self.config.structure_rules.keys()
        for directory, rule in self.config.directory_map.items():
            for r in rule:
                if r not in existing_rules and r not in BUILTIN_DIRECTORY_RULES:
                    raise ConfigurationParseError(
                        f"Directory mapping '{directory}' uses non-existing rule '{r}'"
                    )

    def add_template_rule(
        self, directory: str, rule_name: str, entries: StructureRuleList
    ) -> None:
        """Register an expanded template rule and map it to a directory.

        Args:
            directory: Directory map key the expanded rule applies to.
            rule_name: Name to register the generated structure rule under.
            entries: Parsed entries making up the generated structure rule.
        """
        self.config.structure_rules[rule_name] = entries
        self.config.directory_map.setdefault(directory, []).append(rule_name)

    @property
    def structure_rules(self) -> StructureRuleMap:
        """Property for structure rules."""
        return self.config.structure_rules

    @property
    def directory_map(self) -> DirectoryMap:
        """Property for directory mappings."""
        return self.config.directory_map

    @property
    def configuration_file_name(self) -> str:
        """Property for the top-level configuration file name."""
        return self.config.configuration_file_name

    @property
    def configuration_file_names(self) -> set[str]:
        """Property for every configuration file that took part in the load.

        Holds the top-level configuration file as it was passed in, plus every
        mounted configuration as a repository-root relative path.
        """
        return self.config.configuration_file_names

    @property
    def rule_origins(self) -> dict[str, str]:
        """Property mapping each structure rule to the file that defined it."""
        return self.config.rule_origins

    def configuration_file_names_for(self, repo_root: str) -> set[str]:
        """Names a scan of ``repo_root`` should recognise as configuration files.

        Mounted configurations are already recorded relative to the repository
        root. The top-level configuration is not: it is whatever path the caller
        passed in, so it is additionally offered relative to ``repo_root``.
        """
        names = set(self.config.configuration_file_names)
        root_relative = relative_to_root(self.config.configuration_file_name, repo_root)
        if root_relative:
            names.add(root_relative)
        return names

    @property
    def structure_rule_descriptions(self) -> dict[str, str]:
        """Property for structure rule descriptions."""
        return self.config.structure_rule_descriptions

    @property
    def directory_descriptions(self) -> dict[str, str]:
        """Property for directory descriptions."""
        return self.config.directory_descriptions


def load_document(path: str, schema: dict[Any, Any] | None = None) -> ParsedDocument:
    """Read and parse a single configuration file.

    This is the per-file half of configuration loading: it knows nothing about
    mounted configurations beyond recording them in
    :attr:`ParsedDocument.mounts`. Combining documents is
    ``config_merge``'s job.

    Args:
        path: Filesystem path to the YAML configuration file.
        schema: Optional JSON schema to validate the YAML against.
    """
    yaml_dict = _load_repo_structure_yaml(path)
    if not yaml_dict:
        raise ConfigurationParseError(
            f"Configuration is empty or could not be parsed: {path}"
        )
    return parse_document(yaml_dict, schema)


def parse_document(
    yaml_dict: dict, schema: dict[Any, Any] | None = None
) -> ParsedDocument:
    """Validate and parse one already-loaded configuration document.

    Args:
        yaml_dict: The raw YAML document.
        schema: Optional JSON schema to validate the document against.
    """
    _validate_schema(yaml_dict, schema)

    _LOGGER.debug("Parsing configuration data")
    directory_map_yaml = yaml_dict.get("directory_map", {})
    structure_rules, rule_descriptions = _parse_structure_rules(
        yaml_dict.get("structure_rules", {})
    )
    directory_map, directory_descriptions, mounts = _build_directory_map(
        directory_map_yaml
    )

    document = ParsedDocument(
        structure_rules=structure_rules,
        structure_rule_descriptions=rule_descriptions,
        directory_map=directory_map,
        directory_descriptions=directory_descriptions,
        mounts=mounts,
        inherit=_parse_inherit(yaml_dict.get("inherit", {})),
    )
    _parse_templates_to_document(
        yaml_dict.get("templates", {}), directory_map_yaml, document
    )
    return document


def _validate_schema(yaml_dict: dict, schema: dict[Any, Any] | None) -> None:
    """Validate the raw YAML against the JSON schema."""
    if not schema:
        schema = get_json_schema()

    try:
        validate(instance=yaml_dict, schema=schema)
    except ValidationError as e:
        raise ConfigurationParseError(f"Bad config: {e.message}") from e
    except SchemaError as e:
        raise ConfigurationParseError(f"Bad schema: {e.message}") from e
    _LOGGER.debug("Configuration validated successfully")


def _parse_inherit(inherit_yaml: dict) -> InheritSpec:
    """Parse the ``inherit`` section of a mounted configuration."""
    structure_rules = inherit_yaml.get("structure_rules")
    override = list(inherit_yaml.get("override", []))

    if structure_rules is None and override:
        raise ConfigurationParseError(
            "'inherit.override' requires 'inherit.structure_rules' -- "
            f"nothing is inherited that {', '.join(sorted(override))} could override"
        )

    return InheritSpec(structure_rules=structure_rules, override=override)


def _build_from_yaml_string(
    yaml_string: str, schema: dict[Any, Any] | None
) -> ConfigurationData:
    """Build configuration data from raw YAML text.

    A YAML string has no directory to resolve mounted configuration paths
    against and no parent to inherit from, so both are rejected here.
    """
    _LOGGER.debug("Loading configuration")
    yaml_dict = _load_repo_structure_yamls(yaml_string)
    if not yaml_dict:
        raise ConfigurationParseError(
            "Configuration is empty or could not be parsed: yaml string"
        )

    document = parse_document(yaml_dict, schema)
    if document.mounts:
        raise ConfigurationParseError(
            "'use_config' is only supported when loading from a file, "
            "since the mounted path is resolved relative to the configuration"
        )
    if document.inherit.structure_rules is not None:
        raise ConfigurationParseError(
            "'inherit' is only valid in a configuration mounted through "
            "'use_config' -- there is no parent configuration to inherit from"
        )

    return ConfigurationData(
        structure_rules=document.structure_rules,
        directory_map=document.directory_map,
        structure_rule_descriptions=document.structure_rule_descriptions,
        directory_descriptions=document.directory_descriptions,
    )


def _load_repo_structure_yaml(filename: str) -> dict:
    with open(filename, "r", encoding="utf-8") as file:
        return _load_repo_structure_yamls(file)


def _load_repo_structure_yamls(yaml_string: str | TextIO) -> dict:
    yaml = YAML.YAML(typ="safe")
    return yaml.load(yaml_string)


def _parse_structure_rules(
    structure_rules_yaml: dict,
) -> tuple[StructureRuleMap, dict[str, str]]:

    def _validate_use_rule_not_dangling(rules: StructureRuleMap) -> None:
        for rule_key in rules.keys():
            for entry in rules[rule_key]:
                if entry.use_rule and entry.use_rule not in rules:
                    raise ConfigurationParseError(
                        f"use_rule '{entry.use_rule}' in entry '{entry.path.pattern}'"
                        "is not a valid rule key"
                    )

    def _validate_use_rule_only_recursive(rules: StructureRuleMap) -> None:
        for rule_key in rules.keys():
            for entry in rules[rule_key]:
                if entry.use_rule and entry.use_rule != rule_key:
                    raise ConfigurationParseError(
                        f"use_rule '{entry.use_rule}' in entry '{entry.path.pattern}'"
                        "is not recursive"
                    )

    rules, descriptions = _build_rules(structure_rules_yaml)
    _validate_use_rule_not_dangling(rules)
    _validate_use_rule_only_recursive(rules)

    return rules, descriptions


def _build_rules(
    structure_rules_yaml: dict,
) -> tuple[StructureRuleMap, dict[str, str]]:

    def _parse_directory_structure(
        directory_structure_yaml: list, structure_rule_list: StructureRuleList
    ) -> str:
        """Parse directory structure entries and return the description."""
        if not directory_structure_yaml:
            raise ConfigurationParseError("Structure rule cannot be empty")

        # First entry must be the description
        first_entry = directory_structure_yaml[0]
        if "description" not in first_entry or len(first_entry) != 1:
            raise ConfigurationParseError(
                "First entry in structure rule must be a description object "
                "with only 'description' field"
            )

        description = first_entry["description"]

        # Parse remaining entries (skip the description at index 0)
        for item in directory_structure_yaml[1:]:
            structure_rule_list.append(_parse_entry_to_repo_entry(item))

        return description

    rules: StructureRuleMap = {}
    descriptions: dict[str, str] = {}
    if not structure_rules_yaml:
        return rules, descriptions

    for rule in structure_rules_yaml:
        structure_rules: StructureRuleList = []
        description = _parse_directory_structure(
            structure_rules_yaml[rule], structure_rules
        )
        rules[rule] = structure_rules
        descriptions[rule] = description
    return rules, descriptions


# The keys that carry an entry's pattern, in precedence order - the first
# one present on an entry decides how the entry is treated.
_PATTERN_KEYS = ("require", "allow", "forbid")


class ParsedEntry(NamedTuple):
    """A structure rule entry's pattern together with how it is enforced."""

    pattern: str
    kind: str
    is_required: bool

    @property
    def is_forbidden(self) -> bool:
        """True if the entry's pattern must not match anything."""
        return self.kind == "forbid"


def _classify_entry(entry: dict) -> ParsedEntry:
    """Determine which pattern key an entry uses and what it implies."""
    for kind in _PATTERN_KEYS:
        if kind in entry:
            return ParsedEntry(
                pattern=entry[kind], kind=kind, is_required=kind == "require"
            )
    raise ConfigurationParseError(
        f"Entry must contain one of {', '.join(_PATTERN_KEYS)}: {entry}"
    )


def _parse_entry_to_repo_entry(entry: dict) -> RepoEntry:
    parsed = _classify_entry(entry)
    entry_pattern = parsed.pattern

    is_dir = entry_pattern.endswith("/")
    entry_pattern = entry_pattern[0:-1] if is_dir else entry_pattern

    try:
        compiled_pattern = re.compile(entry_pattern)
    except re.error as e:
        raise StructureRuleError(
            f"Bad pattern {entry_pattern}, failed to compile: {e}"
        ) from e

    result = RepoEntry(
        path=compiled_pattern,
        is_dir=is_dir,
        is_required=parsed.is_required,
        is_forbidden=parsed.is_forbidden,
        use_rule=entry.get("use_rule", ""),
    )
    for sub_entry in entry.get("if_exists", []):
        result.if_exists.append(_parse_entry_to_repo_entry(sub_entry))

    for sub_entry in entry.get("companion", []):
        result.companion.append(_parse_entry_to_repo_entry(sub_entry))

    return result


def _expand_template_entry(
    template_yaml: list[dict], expansion_key: str, expansion_var: str
) -> list[dict]:

    def _expand_entry(entry: dict, expansion_key: str, expansion_var: str):
        # Skip description entries
        if "description" in entry and len(entry) == 1:
            return entry
        k = _classify_entry(entry).kind
        entry[k] = entry[k].replace(f"{{{{{expansion_key}}}}}", expansion_var)
        return entry

    expanded_yaml: list[dict] = []
    for entry in template_yaml:
        entry = _expand_entry(entry, expansion_key, expansion_var)
        if "if_exists" in entry:
            entry["if_exists"] = _expand_template_entry(
                entry["if_exists"], expansion_key, expansion_var
            )
        if "companion" in entry:
            entry["companion"] = _expand_template_entry(
                entry["companion"], expansion_key, expansion_var
            )
        expanded_yaml.append(entry)
    return expanded_yaml


def _parse_use_template(
    dir_map_yaml: dict, directory: str, templates_yaml: dict, document: ParsedDocument
):
    if "use_template" not in dir_map_yaml:
        return

    def _expand_template(dir_map_yaml, templates_yaml):
        expansion_map = dir_map_yaml["parameters"]
        max_values_length = max(
            (len(values) for values in expansion_map.values()), default=0
        )
        structure_rules_yaml: list[dict] = []
        for i in range(max_values_length):
            if dir_map_yaml["use_template"] not in templates_yaml:
                raise TemplateError(
                    f"Template '{dir_map_yaml['use_template']}'"
                    "not found in templates"
                )
            entries = copy.deepcopy(templates_yaml[dir_map_yaml["use_template"]])
            for expansion_key, expansion_vars in expansion_map.items():
                index = i % len(expansion_vars)
                entries = _expand_template_entry(
                    entries, expansion_key, expansion_vars[index]
                )
            structure_rules_yaml.extend(entries)
        return structure_rules_yaml

    structure_rules_yaml = _expand_template(dir_map_yaml, templates_yaml)

    # Filter out description entries before parsing to RepoEntry
    structure_rule_list = [
        _parse_entry_to_repo_entry(entry)
        for entry in structure_rules_yaml
        if not ("description" in entry and len(entry) == 1)
    ]

    template_rule_name = (
        f"__template_rule_{map_dir_to_rel_dir(directory)}_"
        f"{dir_map_yaml['use_template']}"
    )
    document.structure_rules[template_rule_name] = structure_rule_list
    document.directory_map.setdefault(directory, []).append(template_rule_name)


def _build_directory_map(
    directory_map_yaml: dict,
) -> tuple[DirectoryMap, dict[str, str], dict[str, str]]:
    """Parse the ``directory_map`` section.

    Returns the rules mapped to each directory, the directory descriptions and
    the configurations mounted through ``use_config``, keyed by mount directory.
    """

    def _parse_use_config(rule: dict, directory: str, mounts: dict[str, str]) -> None:
        if rule.keys() != {"use_config"}:
            return
        if directory in mounts:
            raise ConfigurationParseError(
                f"Directory mapping '{directory}' mounts more than one "
                "configuration through 'use_config'"
            )
        mounts[directory] = rule["use_config"]

    def _extract_description(value_list: list) -> str:
        """Extract and validate description from directory map entry."""
        if not value_list:
            raise ConfigurationParseError("Directory map entry cannot be empty")

        first_entry = value_list[0]
        if "description" not in first_entry or len(first_entry) != 1:
            raise ConfigurationParseError(
                "First entry in directory map must be a description"
                "object with only 'description' field"
            )

        return first_entry["description"]

    mapping: DirectoryMap = {}
    descriptions: dict[str, str] = {}
    mounts: dict[str, str] = {}

    for directory, value in directory_map_yaml.items():
        description = _extract_description(value)
        descriptions[directory] = description

        for r in value[1:]:  # Skip the description at index 0
            if r.keys() == {"use_rule"}:
                mapping.setdefault(directory, []).append(r["use_rule"])
            else:
                _parse_use_config(r, directory, mounts)

    return mapping, descriptions, mounts


def _parse_templates_to_document(
    templates_yaml: dict, directory_map_yaml: dict, document: ParsedDocument
) -> None:
    for directory, value in directory_map_yaml.items():
        for use_map in value:
            _parse_use_template(use_map, directory, templates_yaml, document)
