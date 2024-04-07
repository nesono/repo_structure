# Repo Kondo

A tool to control your repository structure and keep it clean at all times.

You can control

- What files and directories are allowed (`required` + `optional`)
- Use regexes for specifications
- Map directory structure rules to directories (`directory_mapping`)
- Reuse directory structure rules recursively (`use_rule` in `structure_rules`)
- Differentiate between required and optional files (`required` vs `optinonal`)
- Inherit rules from other rules (`includes`)

The example file show cases all the supported features:
[example yaml](test_config.yaml)
