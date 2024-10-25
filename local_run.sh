#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail

poetry install
poetry run python -m repo_structure --repo-root=. --config-path=repo_structure.yaml
