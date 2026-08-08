"""Tests for merging directory-relative configuration files."""

# pylint: disable=too-few-public-methods

from pathlib import Path

import pytest

from .config import Configuration
from .config_merge import qualify, rebase_map_dir, unqualify
from .errors import ConfigurationParseError
from .full_scan import FullScanProcessor
from .models import Flags
from .test_lib import create_repo_structure

ROOT_CONFIG = "repo_structure.yaml"


def _write_configs(repo_root: str, configs: dict[str, str]) -> str:
    """Write configuration files into a repository and return the top-level one.

    Keys are paths relative to the repository root; the top-level configuration
    is expected under :data:`ROOT_CONFIG`.
    """
    for rel_path, content in configs.items():
        path = Path(repo_root) / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return str(Path(repo_root) / ROOT_CONFIG)


_PARENT_WITH_FRONTEND = """
structure_rules:
  base:
    - description: 'Root files'
    - require: 'README\\.md'
  docs:
    - description: 'Parent documentation rule'
    - allow: '.*\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: base
  /frontend/:
    - description: 'Owned by the frontend team'
    - use_config: repo_structure.yaml
"""


def _build(tmp_path, configs: dict[str, str], tree: str = "") -> Configuration:
    """Create a repository with the given tree and configurations, and load it."""
    repo = create_repo_structure(tmp_path, tree)
    return Configuration.from_file(_write_configs(repo, configs))


class TestQualifiedNames:
    """Test the qualified rule name helpers."""

    def test_qualify_round_trip(self):
        """Test that unqualify recovers the name qualify was given."""
        qualified = qualify("frontend/repo_structure.yaml", "python_package")
        assert qualified == "frontend/repo_structure.yaml::python_package"
        assert unqualify(qualified) == "python_package"

    def test_unqualify_leaves_plain_names_alone(self):
        """Test that a top-level rule name survives unqualify unchanged."""
        assert unqualify("python_package") == "python_package"


class TestRebaseMapDir:
    """Test translating a mounted config's directories into the repository."""

    @pytest.mark.parametrize(
        "mount_dir, child_map_dir, expected",
        [
            ("/frontend/", "/", "/frontend/"),
            ("/frontend/", "/components/", "/frontend/components/"),
            ("/frontend/", "/components/ui/", "/frontend/components/ui/"),
            ("/", "/components/", "/components/"),
            ("/a/b/", "/c/", "/a/b/c/"),
        ],
    )
    def test_rebase_map_dir(self, mount_dir, child_map_dir, expected):
        """Test that a mounted directory map is rebased under its mount point."""
        assert rebase_map_dir(mount_dir, child_map_dir) == expected


class TestMounting:
    """Test mounting a configuration through use_config."""

    def test_mounted_rules_and_directories_are_merged(self, tmp_path):
        """Test that a mounted configuration contributes rules and mappings."""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
structure_rules:
  ts_package:
    - description: 'TypeScript package'
    - require: 'index\\.ts'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: ts_package
  /components/:
    - description: 'Components'
    - use_rule: ts_package
""",
            },
        )

        mounted = "frontend/repo_structure.yaml::ts_package"
        assert config.directory_map == {
            "/": ["base"],
            "/frontend/": [mounted],
            "/frontend/components/": [mounted],
        }
        assert mounted in config.structure_rules
        assert config.rule_origins[mounted] == "frontend/repo_structure.yaml"

    def test_mounted_config_description_wins(self, tmp_path):
        """Test that the mounted config describes the directory it owns."""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
structure_rules:
  ts_package:
    - description: 'TypeScript package'
    - require: 'index\\.ts'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: ts_package
""",
            },
        )
        assert config.directory_descriptions["/frontend/"] == "Frontend root"

    def test_sibling_configs_may_share_rule_names(self, tmp_path):
        """Test that two mounted configs can define the same rule name."""
        same_rule = """
structure_rules:
  package:
    - description: 'A package'
    - require: 'main\\.py'
directory_map:
  /:
    - description: 'Team root'
    - use_rule: package
"""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: """
structure_rules:
  base:
    - description: 'Root files'
    - require: 'README\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: base
  /frontend/:
    - description: 'Frontend'
    - use_config: repo_structure.yaml
  /backend/:
    - description: 'Backend'
    - use_config: repo_structure.yaml
""",
                "frontend/repo_structure.yaml": same_rule,
                "backend/repo_structure.yaml": same_rule,
            },
        )

        assert config.directory_map["/frontend/"] == [
            "frontend/repo_structure.yaml::package"
        ]
        assert config.directory_map["/backend/"] == [
            "backend/repo_structure.yaml::package"
        ]

    def test_recursive_use_rule_is_rewritten(self, tmp_path):
        """Test that recursion inside a mounted rule points at the merged name."""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
structure_rules:
  nested:
    - description: 'Recursive rule'
    - require: 'index\\.ts'
    - allow: '.*/'
      use_rule: nested
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: nested
""",
            },
        )

        qualified = "frontend/repo_structure.yaml::nested"
        recursion = [e for e in config.structure_rules[qualified] if e.use_rule]
        assert [e.use_rule for e in recursion] == [qualified]

    def test_nested_mounts(self, tmp_path):
        """Test that a mounted configuration can mount another one."""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
structure_rules:
  ts_package:
    - description: 'TypeScript package'
    - require: 'index\\.ts'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: ts_package
  /ui/:
    - description: 'Owned by the design system team'
    - use_config: repo_structure.yaml
""",
                "frontend/ui/repo_structure.yaml": """
structure_rules:
  widgets:
    - description: 'Widgets'
    - require: 'button\\.ts'
directory_map:
  /:
    - description: 'UI root'
    - use_rule: widgets
""",
            },
        )

        assert config.directory_map["/frontend/ui/"] == [
            "frontend/ui/repo_structure.yaml::widgets"
        ]


class TestInheritance:
    """Test inheriting structure rules from the mounting configuration."""

    def test_inherit_all(self, tmp_path):
        """Test that 'structure_rules: all' makes every parent rule usable."""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
inherit:
  structure_rules: all
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: docs
""",
            },
        )

        # Inheriting aliases the parent's rule rather than copying it.
        assert config.directory_map["/frontend/"] == ["docs"]
        assert "frontend/repo_structure.yaml::docs" not in config.structure_rules

    def test_inherit_selected_rules(self, tmp_path):
        """Test that an explicit list inherits exactly the named rules."""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
inherit:
  structure_rules: [docs]
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: docs
""",
            },
        )
        assert config.directory_map["/frontend/"] == ["docs"]

    def test_inheritance_chains_through_nested_mounts(self, tmp_path):
        """Test that a rule inherited by a parent stays inheritable further down."""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
inherit:
  structure_rules: all
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: docs
  /ui/:
    - description: 'Design system'
    - use_config: repo_structure.yaml
""",
                "frontend/ui/repo_structure.yaml": """
inherit:
  structure_rules: [docs]
directory_map:
  /:
    - description: 'UI root'
    - use_rule: docs
""",
            },
        )
        assert config.directory_map["/frontend/ui/"] == ["docs"]

    def test_override_redefines_only_for_the_child(self, tmp_path):
        """Test that an overridden rule replaces the inherited one in the child."""
        config = _build(
            tmp_path,
            {
                ROOT_CONFIG: """
structure_rules:
  docs:
    - description: 'Parent documentation rule'
    - allow: '.*\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: docs
  /frontend/:
    - description: 'Frontend'
    - use_config: repo_structure.yaml
""",
                "frontend/repo_structure.yaml": """
inherit:
  structure_rules: all
  override: [docs]
structure_rules:
  docs:
    - description: 'Frontend documentation rule'
    - require: 'GUIDE\\.md'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: docs
""",
            },
        )

        assert config.directory_map["/"] == ["docs"]
        assert config.directory_map["/frontend/"] == [
            "frontend/repo_structure.yaml::docs"
        ]
        assert [e.path.pattern for e in config.structure_rules["docs"]] == [r".*\.md"]
        assert [
            e.path.pattern
            for e in config.structure_rules["frontend/repo_structure.yaml::docs"]
        ] == [r"GUIDE\.md"]


class TestCollisions:
    """Test that ambiguity between configurations is reported as an error."""

    def test_redefining_an_inherited_rule_without_override(self, tmp_path):
        """Test that shadowing an inherited rule by accident is an error."""
        with pytest.raises(ConfigurationParseError, match="collide with inherited"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                    "frontend/repo_structure.yaml": """
inherit:
  structure_rules: all
structure_rules:
  docs:
    - description: 'Frontend documentation rule'
    - require: 'GUIDE\\.md'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: docs
""",
                },
            )

    def test_override_of_a_rule_that_is_not_inherited(self, tmp_path):
        """Test that overriding something never inherited is an error."""
        with pytest.raises(ConfigurationParseError, match="not inherited"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                    "frontend/repo_structure.yaml": """
inherit:
  structure_rules: [docs]
  override: [base]
structure_rules:
  base:
    - description: 'Frontend base'
    - require: 'index\\.ts'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: base
""",
                },
            )

    def test_inheriting_an_unknown_rule(self, tmp_path):
        """Test that inheriting a rule the parent does not define is an error."""
        with pytest.raises(ConfigurationParseError, match="does not define"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                    "frontend/repo_structure.yaml": """
inherit:
  structure_rules: [nonexistent]
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: nonexistent
""",
                },
            )

    def test_two_configurations_claiming_one_directory(self, tmp_path):
        """Test that two configurations mapping the same directory is an error."""
        with pytest.raises(ConfigurationParseError, match="claimed by more than one"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: """
structure_rules:
  base:
    - description: 'Root files'
    - require: 'README\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: base
  /frontend/components/:
    - description: 'Claimed by the root configuration too'
    - use_rule: base
  /frontend/:
    - description: 'Frontend'
    - use_config: repo_structure.yaml
""",
                    "frontend/repo_structure.yaml": """
structure_rules:
  components:
    - description: 'Components'
    - require: 'button\\.ts'
directory_map:
  /components/:
    - description: 'Components'
    - use_rule: components
""",
                },
            )

    def test_directory_mapping_that_traverses_upwards(self, tmp_path):
        """Test that a mounted config cannot climb out of its own subtree."""
        with pytest.raises(ConfigurationParseError, match="traverse"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                    "frontend/repo_structure.yaml": """
structure_rules:
  escape:
    - description: 'Reaches outside the frontend'
    - require: 'anything'
directory_map:
  /../backend/:
    - description: 'Not mine to govern'
    - use_rule: escape
""",
                },
            )

    def test_use_config_path_that_traverses_upwards(self, tmp_path):
        """Test that use_config must point below the directory it applies to."""
        with pytest.raises(ConfigurationParseError, match="must be a relative path"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: """
structure_rules:
  base:
    - description: 'Root files'
    - require: 'README\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: base
  /frontend/:
    - description: 'Frontend'
    - use_config: ../elsewhere/repo_structure.yaml
""",
                },
            )

    def test_mounting_the_same_configuration_twice(self, tmp_path):
        """Test that reaching one configuration from two mounts is an error.

        Mount paths may not traverse upwards, so two mounts can only land on
        the same file through a symlink.
        """
        with pytest.raises(ConfigurationParseError, match="mounted more than once"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: """
structure_rules:
  base:
    - description: 'Root files'
    - require: 'README\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: base
  /frontend/:
    - description: 'Frontend'
    - use_config: repo_structure.yaml
  /backend/:
    - description: 'Backend'
    - use_config: repo_structure.yaml
""",
                    "shared/repo_structure.yaml": """
structure_rules:
  package:
    - description: 'A package'
    - require: 'main\\.py'
directory_map:
  /:
    - description: 'Team root'
    - use_rule: package
""",
                },
                """
shared/
frontend -> shared
backend -> shared
""",
            )

    def test_mount_cycle(self, tmp_path):
        """Test that a configuration reachable from itself is an error."""
        with pytest.raises(ConfigurationParseError, match="mounted more than once"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: """
structure_rules:
  base:
    - description: 'Root files'
    - require: 'README\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: base
  /self/:
    - description: 'Loops back onto the top-level configuration'
    - use_config: repo_structure.yaml
"""
                },
                """
self -> .
""",
            )

    def test_directory_both_maps_rules_and_mounts_a_configuration(self, tmp_path):
        """Test that a directory cannot be governed twice by one configuration."""
        with pytest.raises(ConfigurationParseError, match="both maps structure rules"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: """
structure_rules:
  base:
    - description: 'Root files'
    - require: 'README\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: base
  /frontend/:
    - description: 'Frontend'
    - use_rule: base
    - use_config: repo_structure.yaml
""",
                    "frontend/repo_structure.yaml": """
structure_rules:
  ts_package:
    - description: 'TypeScript package'
    - require: 'index\\.ts'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: ts_package
""",
                },
            )

    def test_missing_mounted_configuration(self, tmp_path):
        """Test that mounting a configuration that is not there is an error."""
        with pytest.raises(ConfigurationParseError, match="does not exist"):
            _build(tmp_path, {ROOT_CONFIG: _PARENT_WITH_FRONTEND})

    def test_inherit_in_a_top_level_configuration(self, tmp_path):
        """Test that inheriting without a parent to inherit from is an error."""
        with pytest.raises(ConfigurationParseError, match="no parent to inherit from"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: """
inherit:
  structure_rules: all
structure_rules:
  base:
    - description: 'Root files'
    - require: 'README\\.md'
directory_map:
  /:
    - description: 'Root'
    - use_rule: base
"""
                },
            )

    def test_override_without_inheriting(self, tmp_path):
        """Test that an override list without inheritance is an error."""
        with pytest.raises(ConfigurationParseError, match="requires 'inherit"):
            _build(
                tmp_path,
                {
                    ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                    "frontend/repo_structure.yaml": """
inherit:
  override: [docs]
structure_rules:
  docs:
    - description: 'Frontend documentation rule'
    - require: 'GUIDE\\.md'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: docs
""",
                },
            )

    def test_use_config_is_rejected_for_yaml_strings(self):
        """Test that use_config needs a file, since its path is config relative."""
        with pytest.raises(
            ConfigurationParseError, match="only supported when loading"
        ):
            Configuration.from_yaml_string(_PARENT_WITH_FRONTEND)


class TestScanningWithMountedConfigurations:
    """Test that scans honour every configuration taking part in the load."""

    def _scan(self, tmp_path, configs, tree):
        repo = create_repo_structure(tmp_path, tree)
        config = Configuration.from_file(_write_configs(repo, configs))
        return FullScanProcessor(repo, config, Flags()).scan()

    def test_mounted_configuration_governs_its_subtree(self, tmp_path):
        """Test that a violation below a mount point is found and located."""
        result = self._scan(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
structure_rules:
  ts_package:
    - description: 'TypeScript package'
    - require: 'index\\.ts'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: ts_package
""",
            },
            """
README.md
frontend/
frontend/index.ts
frontend/stray.txt
""",
        )

        assert [(e.code, e.path) for e in result.errors] == [
            ("unspecified_entry", "frontend/stray.txt")
        ]

    def test_mounted_configuration_files_are_not_reported(self, tmp_path):
        """Test that the configuration files themselves are skipped."""
        result = self._scan(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
structure_rules:
  ts_package:
    - description: 'TypeScript package'
    - require: 'index\\.ts'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: ts_package
""",
            },
            """
README.md
frontend/
frontend/index.ts
""",
        )

        assert result.is_success

    def test_unused_mounted_rule_names_its_configuration(self, tmp_path):
        """Test that an unused rule is reported with the file that defines it."""
        result = self._scan(
            tmp_path,
            {
                ROOT_CONFIG: _PARENT_WITH_FRONTEND,
                "frontend/repo_structure.yaml": """
structure_rules:
  ts_package:
    - description: 'TypeScript package'
    - require: 'index\\.ts'
  unused:
    - description: 'Never mapped anywhere'
    - require: 'nothing'
directory_map:
  /:
    - description: 'Frontend root'
    - use_rule: ts_package
""",
            },
            """
README.md
frontend/
frontend/index.ts
""",
        )

        messages = [w.message for w in result.warnings]
        assert messages == [
            "Unused structure rule 'docs'",
            "Unused structure rule 'unused' in 'frontend/repo_structure.yaml'",
        ]
