"""Ensure clean repository structure for your projects."""

import pprint

from repo_structure_config import Configuration


if __name__ == "__main__":
    FILENAME = "test_config.yaml"
    config = Configuration(FILENAME)
    pprint.pprint(config.structure_rules)
    pprint.pprint(config.directory_mappings)
