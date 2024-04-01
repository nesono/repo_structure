from repo_structure import load_repo_structure_yaml, parse_structure_rules

if __name__ == "__main__":
    filename = "test_config.yaml"
    cfg = load_repo_structure_yaml(filename)
    config = load_repo_structure_yaml(filename)
    structure_rules = parse_structure_rules(config["structure_rules"])
    print(structure_rules)
