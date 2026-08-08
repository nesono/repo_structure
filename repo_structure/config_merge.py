"""Combining several configuration documents into one flat configuration.

A repository can split its configuration across directories: a ``directory_map``
entry mounts another configuration file with ``use_config``, and that file
describes its own subtree using paths relative to itself. This module walks that
mount tree and flattens it into a single :class:`ConfigurationData`, so nothing
downstream of ``Configuration`` has to know that more than one file was read.

Two ideas carry the whole merge:

*Qualification.* Rules from a mounted configuration are stored under
``"<config path>::<rule name>"``, so two teams may both define ``python_package``
without ever colliding. Rules of the top-level configuration keep their bare
names, which is what makes a single-file configuration merge to exactly what it
parsed to.

*Inheritance is aliasing.* ``inherit.structure_rules`` does not copy a parent
rule -- it only makes the parent's qualified name reachable under its bare name
inside the child. Redefining an inherited rule therefore has to be spelled out
in ``inherit.override``; anything else is reported as a collision.
"""

import logging
from pathlib import Path, PurePosixPath
from typing import Callable

from .errors import ConfigurationParseError
from .models import (
    ConfigurationData,
    InheritSpec,
    ParsedDocument,
    StructureRuleList,
)
from .paths import (
    join_path_normalized,
    map_dir_to_rel_dir,
    normalize_path,
    rel_dir_to_map_dir,
)

_LOGGER = logging.getLogger(__name__)

QUALIFIER = "::"
"""Separates a configuration path from a rule name in a qualified rule name."""

DocumentLoader = Callable[[str], ParsedDocument]
"""Reads and parses one configuration file. Injected so that this module stays
independent of the parser -- see ``config.load_document``."""


def qualify(config_path: str, rule_name: str) -> str:
    """Build the merged-namespace name of a rule owned by a mounted config."""
    return f"{config_path}{QUALIFIER}{rule_name}"


def unqualify(rule_name: str) -> str:
    """Return the rule name as written in its own configuration file.

    Bare names are returned unchanged, so this is safe to call on any rule name
    taken from a merged configuration.
    """
    return rule_name.rsplit(QUALIFIER, 1)[-1]


def rebase_map_dir(mount_dir: str, child_map_dir: str) -> str:
    """Translate a mounted config's directory into the repository's namespace.

    ``child_map_dir`` is relative to the mounted configuration, where ``/`` is
    the directory the configuration was mounted at.
    """
    if child_map_dir == "/":
        return mount_dir

    return rel_dir_to_map_dir(
        join_path_normalized(
            map_dir_to_rel_dir(mount_dir), map_dir_to_rel_dir(child_map_dir)
        )
    )


def build_config_tree(root_config_path: str, load: DocumentLoader) -> ConfigurationData:
    """Load a configuration file and everything it mounts, as one configuration.

    Args:
        root_config_path: Path to the top-level configuration file.
        load: Reads and parses a single configuration file.

    Exceptions:
        ConfigurationParseError: Raised for any collision between the
            participating configurations -- see the module docstring.
    """
    return _TreeMerger(load).build(root_config_path)


class _TreeMerger:  # pylint: disable=too-few-public-methods
    """Walks the mount tree, accumulating one flat ConfigurationData.

    A class rather than a function because the walk carries state across the
    recursion: the accumulated configuration and the set of files already
    mounted.
    """

    def __init__(self, load: DocumentLoader):
        self._load = load
        self._data = ConfigurationData()
        # Resolved config path -> the directory it was first mounted at. Doubles
        # as the guard against mount cycles and against mounting twice.
        self._visited: dict[str, str] = {}

    def build(self, root_config_path: str) -> ConfigurationData:
        """Merge the configuration at ``root_config_path`` and its mounts."""
        self._data.configuration_file_name = root_config_path
        self._data.configuration_file_names.add(normalize_path(root_config_path))

        self._merge(root_config_path, None, "/", {})

        if root_config_path in self._data.structure_rules:
            raise ConfigurationParseError(
                f"Conflicting Structure rule for {root_config_path}"
                "- do not add the config manually."
            )
        return self._data

    def _merge(
        self,
        fs_path: str,
        rel_path: str | None,
        mount_dir: str,
        exported: dict[str, str],
    ) -> None:
        """Merge one configuration file and, recursively, the ones it mounts.

        Args:
            fs_path: Path the configuration is read from.
            rel_path: The configuration's path relative to the repository root,
                or None for the top-level configuration, whose rules stay
                unqualified.
            mount_dir: Directory this configuration's ``directory_map`` is
                relative to.
            exported: Rule names the mounting configuration offers for
                inheritance, mapped to their qualified names.
        """
        self._mark_visited(fs_path, mount_dir)

        _LOGGER.debug("Merging configuration '%s' mounted at '%s'", fs_path, mount_dir)
        document = self._load(fs_path)

        if rel_path is None and document.inherit.structure_rules is not None:
            raise ConfigurationParseError(
                f"Configuration '{fs_path}' declares 'inherit', but it is not "
                "mounted through 'use_config' and so has no parent to inherit from"
            )

        resolution = _resolve_rule_names(document, rel_path, exported, fs_path)
        self._register_rules(document, resolution, rel_path or fs_path)
        self._register_directory_map(document, resolution, mount_dir, fs_path)
        self._mount_children(document, fs_path, mount_dir, _exportable(resolution))

    def _mark_visited(self, fs_path: str, mount_dir: str) -> None:
        identity = str(Path(fs_path).resolve())
        previous_mount = self._visited.get(identity)
        if previous_mount is not None:
            raise ConfigurationParseError(
                f"Configuration '{fs_path}' is mounted more than once "
                f"(already mounted at '{previous_mount}', now at '{mount_dir}')"
            )
        self._visited[identity] = mount_dir

    def _register_rules(
        self, document: ParsedDocument, resolution: dict[str, str], origin: str
    ) -> None:
        for name, entries in document.structure_rules.items():
            qualified = resolution[name]
            _rewrite_use_rules(entries, resolution)
            self._data.structure_rules[qualified] = entries
            self._data.structure_rule_descriptions[qualified] = (
                document.structure_rule_descriptions.get(name, "")
            )
            self._data.rule_origins[qualified] = origin

    def _register_directory_map(
        self,
        document: ParsedDocument,
        resolution: dict[str, str],
        mount_dir: str,
        fs_path: str,
    ) -> None:
        for child_map_dir, description in document.directory_descriptions.items():
            self._data.directory_descriptions[
                rebase_map_dir(mount_dir, child_map_dir)
            ] = description

        for child_map_dir, rules in document.directory_map.items():
            _validate_map_dir_stays_below(child_map_dir, fs_path)
            if child_map_dir in document.mounts:
                raise ConfigurationParseError(
                    f"Directory mapping '{child_map_dir}' in '{fs_path}' both maps "
                    "structure rules and mounts a configuration through 'use_config'"
                )

            target = rebase_map_dir(mount_dir, child_map_dir)
            if target in self._data.directory_map:
                raise ConfigurationParseError(
                    f"Directory mapping '{target}' is claimed by more than one "
                    f"configuration -- '{fs_path}' maps it as '{child_map_dir}'"
                )
            self._data.directory_map[target] = [
                resolution.get(rule, rule) for rule in rules
            ]

    def _mount_children(
        self,
        document: ParsedDocument,
        fs_path: str,
        mount_dir: str,
        exported: dict[str, str],
    ) -> None:
        parent_dir = str(Path(fs_path).parent)
        for child_map_dir, child_config in document.mounts.items():
            _validate_mounted_path(child_config, child_map_dir, fs_path)

            mount_target = rebase_map_dir(mount_dir, child_map_dir)
            child_rel_dir = map_dir_to_rel_dir(child_map_dir)
            child_fs_path = join_path_normalized(
                parent_dir, child_rel_dir, child_config
            )
            child_rel_path = join_path_normalized(
                map_dir_to_rel_dir(mount_target), child_config
            )

            if not Path(child_fs_path).is_file():
                raise ConfigurationParseError(
                    f"Directory mapping '{child_map_dir}' in '{fs_path}' mounts "
                    f"'{child_config}', but '{child_fs_path}' does not exist"
                )

            self._data.configuration_file_names.add(child_rel_path)
            self._merge(child_fs_path, child_rel_path, mount_target, exported)


def _resolve_rule_names(
    document: ParsedDocument,
    rel_path: str | None,
    exported: dict[str, str],
    fs_path: str,
) -> dict[str, str]:
    """Map every rule name this document may use to its merged-namespace name."""
    inherited = _inherited_names(document.inherit, exported, fs_path)
    override = set(document.inherit.override)

    unknown_override = sorted(override - set(inherited))
    if unknown_override:
        raise ConfigurationParseError(
            f"'inherit.override' in '{fs_path}' names structure rules that are "
            f"not inherited: {', '.join(unknown_override)}"
        )

    clashes = sorted(
        name
        for name in document.structure_rules
        if name in inherited and name not in override
    )
    if clashes:
        raise ConfigurationParseError(
            f"Structure rules in '{fs_path}' collide with inherited rules of the "
            f"same name: {', '.join(clashes)}. Add them to 'inherit.override' to "
            "redefine them deliberately."
        )

    resolution = dict(inherited)
    for name in document.structure_rules:
        resolution[name] = qualify(rel_path, name) if rel_path else name
    return resolution


def _inherited_names(
    inherit: InheritSpec, exported: dict[str, str], fs_path: str
) -> dict[str, str]:
    """Resolve the ``inherit.structure_rules`` request against what is on offer."""
    if inherit.structure_rules is None:
        return {}

    if inherit.inherits_everything:
        return dict(exported)

    requested = list(inherit.structure_rules)
    missing = sorted(name for name in requested if name not in exported)
    if missing:
        raise ConfigurationParseError(
            f"'inherit.structure_rules' in '{fs_path}' names structure rules the "
            f"mounting configuration does not define: {', '.join(missing)}"
        )
    return {name: exported[name] for name in requested}


def _exportable(resolution: dict[str, str]) -> dict[str, str]:
    """Drop generated rules, which are not meaningful to inherit."""
    return {
        name: qualified
        for name, qualified in resolution.items()
        if not name.startswith("__")
    }


def _rewrite_use_rules(entries: StructureRuleList, resolution: dict[str, str]) -> None:
    """Point every ``use_rule`` at its merged-namespace name, in place.

    Entries come straight out of the parser and belong to this document alone,
    so rewriting them is not visible anywhere else.
    """
    for entry in entries:
        if entry.use_rule:
            entry.use_rule = resolution.get(entry.use_rule, entry.use_rule)
        _rewrite_use_rules(entry.if_exists, resolution)
        _rewrite_use_rules(entry.companion, resolution)


def _validate_mounted_path(child_config: str, child_map_dir: str, fs_path: str) -> None:
    """Reject mounts that would reach outside the directory they apply to."""
    path = PurePosixPath(normalize_path(child_config))
    if path.is_absolute() or ".." in path.parts:
        raise ConfigurationParseError(
            f"'use_config' for '{child_map_dir}' in '{fs_path}' must be a relative "
            f"path below that directory, got '{child_config}'"
        )
    _validate_map_dir_stays_below(child_map_dir, fs_path)


def _validate_map_dir_stays_below(map_dir: str, fs_path: str) -> None:
    """Reject a directory mapping that climbs out of the configuration's subtree.

    A mounted configuration owns the directory it was mounted at, so a mapping
    that traverses upwards would let it govern a subtree it was not given.
    """
    if ".." in map_dir_to_rel_dir(map_dir).split("/"):
        raise ConfigurationParseError(
            f"Directory mapping '{map_dir}' in '{fs_path}' must not traverse "
            "upwards with '..'"
        )
