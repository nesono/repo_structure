from repo_structure import load_repo_structure_yaml, parse_directory_structure

if __name__ == '__main__':
    filename = "test_config.yaml"
    cfg = load_repo_structure_yaml(filename)
    config = load_repo_structure_yaml(filename)
    structure = parse_directory_structure(config["structure_rules"]["python_package"]["required"])
    print(structure)
