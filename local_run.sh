#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail

PY_VERSION=3.12
PY_BINARY="$(which python${PY_VERSION})" || PY_BINARY=true

if [[ $($PY_BINARY --version) != "Python ${PY_VERSION}"* ]]; then
  echo "Error: Python ${PY_VERSION} binary not found" >&2
  exit 1
fi

trap 'echo "An error occurred. Exiting..." >&2; deactivate; exit 1' ERR
trap 'rm -rf .temp_venv' EXIT

$PY_BINARY -m venv .temp_venv
source .temp_venv/bin/activate

{
  pip install -r requirements_lock.txt > pip_install.log 2>&1
} || {
  echo "Failed to install dependencies" >&2
  exit 1
}
rm -f pip_install.log

python main.py --repo-root=. --config-path=repo_structure_config.yaml
