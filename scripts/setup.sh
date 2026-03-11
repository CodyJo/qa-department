#!/usr/bin/env bash
# Back Office setup wrapper

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"
python3 scripts/backoffice_setup.py "$@"
