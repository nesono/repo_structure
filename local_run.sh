#!/usr/bin/env bash
set -o errexit -o nounset -o pipefail

PY_VERSION=3.12
PY_BINARY="$(which python${PY_VERSION})" || PY_BINARY=true

if [[ $($PY_BINARY --version) != "Python ${PY_VERSION}"* ]]; then
  echo "Error: Python ${PY_VERSION} binary not found" >&2
  exit 1
fi

trap 'deactivate; exit 1' ERR
trap 'rm -rf .temp_venv; rm -f pip_install.log' EXIT

$PY_BINARY -m venv .temp_venv
source .temp_venv/bin/activate

{
  pip install -r requirements.txt > pip_install.log 2>&1
} || {
  echo "Failed to install dependencies" >&2
  cat pip_install.log
  exit 1
}
rm -f pip_install.log

python -m repo_structure --verbose --repo-root=. --config-path=repo_structure_config.yaml
