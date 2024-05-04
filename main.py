"""Ensure clean repository structure for your projects."""

import pprint

from repo_structure import _load_repo_structure_yaml, _parse_structure_rules


if __name__ == "__main__":
    FILENAME = "test_config.yaml"
    config = _load_repo_structure_yaml(FILENAME)
    structure_rules = _parse_structure_rules(config["structure_rules"])
    pprint.pprint(structure_rules)
