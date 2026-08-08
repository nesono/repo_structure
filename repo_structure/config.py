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
from .paths import map_dir_to_rel_dir
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
        """Names a scan of ``repo_root`` should recognise as configuration files."""
        return self.config.configuration_file_names_for(repo_root)

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
    _add_template_rules(yaml_dict.get("templates", {}), directory_map_yaml, document)
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


def _is_description(entry: dict) -> bool:
    """True if a YAML entry is the description object and nothing else."""
    return "description" in entry and len(entry) == 1


def _take_description(entries: list[dict], context: str) -> tuple[str, list[dict]]:
    """Split a section into its leading description and the entries that follow.

    Both structure rules and directory maps are written as a list whose first
    element carries the description, so both are read the same way here.

    Args:
        entries: The raw YAML list.
        context: What is being parsed, for the error messages.
    """
    if not entries:
        raise ConfigurationParseError(f"{context} cannot be empty")

    if not _is_description(entries[0]):
        raise ConfigurationParseError(
            f"First entry in {context.lower()} must be a description object "
            "with only 'description' field"
        )

    return entries[0]["description"], entries[1:]


def _parse_structure_rules(
    structure_rules_yaml: dict,
) -> tuple[StructureRuleMap, dict[str, str]]:
    """Parse the ``structure_rules`` section into rules and their descriptions."""
    rules: StructureRuleMap = {}
    descriptions: dict[str, str] = {}

    for rule_name, rule_yaml in structure_rules_yaml.items():
        description, entries = _take_description(rule_yaml, "Structure rule")
        rules[rule_name] = [_parse_entry_to_repo_entry(entry) for entry in entries]
        descriptions[rule_name] = description

    _validate_use_rules(rules)
    return rules, descriptions


def _validate_use_rules(rules: StructureRuleMap) -> None:
    """Reject a ``use_rule`` that names an unknown rule or a different one.

    A ``use_rule`` may only point back at the rule it appears in: it exists to
    describe recursion, not to compose rules.
    """
    for rule_key, entries in rules.items():
        for entry in entries:
            if not entry.use_rule:
                continue
            if entry.use_rule not in rules:
                raise ConfigurationParseError(
                    f"use_rule '{entry.use_rule}' in entry '{entry.path.pattern}'"
                    "is not a valid rule key"
                )
            if entry.use_rule != rule_key:
                raise ConfigurationParseError(
                    f"use_rule '{entry.use_rule}' in entry '{entry.path.pattern}'"
                    "is not recursive"
                )


# The keys that carry an entry's pattern, in precedence order - the first
# one present on an entry decides how the entry is treated.
_PATTERN_KEYS = ("require", "allow", "forbid")


class ParsedEntry(NamedTuple):
    """A structure rule entry's pattern together with how it is enforced.

    ``kind`` is the pattern key the entry was written with; what it means for
    the scan follows from it, so it is derived rather than stored twice.
    """

    pattern: str
    kind: str

    @property
    def is_required(self) -> bool:
        """True if the entry's pattern must match at least once."""
        return self.kind == "require"

    @property
    def is_forbidden(self) -> bool:
        """True if the entry's pattern must not match anything."""
        return self.kind == "forbid"


def _classify_entry(entry: dict) -> ParsedEntry:
    """Determine which pattern key an entry uses and what it implies."""
    for kind in _PATTERN_KEYS:
        if kind in entry:
            return ParsedEntry(pattern=entry[kind], kind=kind)
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


def _substitute_in_entry(entry: dict, expansion_key: str, expansion_var: str) -> dict:
    """Replace ``{{key}}`` with one expansion value in a single template entry."""
    if _is_description(entry):
        return entry
    kind = _classify_entry(entry).kind
    entry[kind] = entry[kind].replace(f"{{{{{expansion_key}}}}}", expansion_var)
    return entry


def _expand_template_entry(
    template_yaml: list[dict], expansion_key: str, expansion_var: str
) -> list[dict]:
    """Substitute one expansion value throughout a template's entries."""
    expanded_yaml: list[dict] = []
    for entry in template_yaml:
        entry = _substitute_in_entry(entry, expansion_key, expansion_var)
        for nested in ("if_exists", "companion"):
            if nested in entry:
                entry[nested] = _expand_template_entry(
                    entry[nested], expansion_key, expansion_var
                )
        expanded_yaml.append(entry)
    return expanded_yaml


def _expand_template(dir_map_yaml: dict, templates_yaml: dict) -> list[dict]:
    """Instantiate a template once per value of its longest parameter list.

    Parameters shorter than the longest one repeat cyclically, so a template
    parameterized by two lists of unequal length still yields one entry set per
    instantiation.
    """
    template_name = dir_map_yaml["use_template"]
    if template_name not in templates_yaml:
        raise TemplateError(f"Template '{template_name}'" "not found in templates")

    expansion_map = dir_map_yaml["parameters"]
    instantiations = max((len(values) for values in expansion_map.values()), default=0)

    structure_rules_yaml: list[dict] = []
    for i in range(instantiations):
        entries = copy.deepcopy(templates_yaml[template_name])
        for expansion_key, expansion_vars in expansion_map.items():
            entries = _expand_template_entry(
                entries, expansion_key, expansion_vars[i % len(expansion_vars)]
            )
        structure_rules_yaml.extend(entries)
    return structure_rules_yaml


def _parse_use_template(
    dir_map_yaml: dict, directory: str, templates_yaml: dict
) -> tuple[str, StructureRuleList] | None:
    """Expand a ``use_template`` entry into a generated rule.

    Returns the generated rule's name and entries, or None if the directory map
    entry does not use a template at all.
    """
    if "use_template" not in dir_map_yaml:
        return None

    structure_rules_yaml = _expand_template(dir_map_yaml, templates_yaml)

    template_rule_name = (
        f"__template_rule_{map_dir_to_rel_dir(directory)}_"
        f"{dir_map_yaml['use_template']}"
    )
    entries = [
        _parse_entry_to_repo_entry(entry)
        for entry in structure_rules_yaml
        if not _is_description(entry)
    ]
    return template_rule_name, entries


def _build_directory_map(
    directory_map_yaml: dict,
) -> tuple[DirectoryMap, dict[str, str], dict[str, str]]:
    """Parse the ``directory_map`` section.

    Returns the rules mapped to each directory, the directory descriptions and
    the configurations mounted through ``use_config``, keyed by mount directory.
    """

    def _record_mount(rule: dict, directory: str) -> None:
        if rule.keys() != {"use_config"}:
            return
        if directory in mounts:
            raise ConfigurationParseError(
                f"Directory mapping '{directory}' mounts more than one "
                "configuration through 'use_config'"
            )
        mounts[directory] = rule["use_config"]

    mapping: DirectoryMap = {}
    descriptions: dict[str, str] = {}
    mounts: dict[str, str] = {}

    for directory, value in directory_map_yaml.items():
        description, entries = _take_description(value, "Directory map entry")
        descriptions[directory] = description

        for entry in entries:
            if entry.keys() == {"use_rule"}:
                mapping.setdefault(directory, []).append(entry["use_rule"])
            else:
                _record_mount(entry, directory)

    return mapping, descriptions, mounts


def _add_template_rules(
    templates_yaml: dict, directory_map_yaml: dict, document: ParsedDocument
) -> None:
    """Register a generated rule for every ``use_template`` in the directory map."""
    for directory, value in directory_map_yaml.items():
        for use_map in value:
            expanded = _parse_use_template(use_map, directory, templates_yaml)
            if expanded is None:
                continue
            rule_name, entries = expanded
            document.structure_rules[rule_name] = entries
            document.directory_map.setdefault(directory, []).append(rule_name)
