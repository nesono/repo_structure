"""Ensure clean repository structure for your projects."""

from repo_structure import load_repo_structure_yaml, parse_structure_rules


if __name__ == "__main__":
    FILENAME = "test_config.yaml"
    cfg = load_repo_structure_yaml(FILENAME)
    config = load_repo_structure_yaml(FILENAME)
    structure_rules = parse_structure_rules(config["structure_rules"])
    print(structure_rules)
