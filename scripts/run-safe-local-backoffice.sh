#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8070}"
TARGETS="${TARGETS:-}"
NO_SERVE=false
LIST_ONLY=false

usage() {
  cat <<'EOF'
Usage: scripts/run-safe-local-backoffice.sh [options]

Safe local Back Office runner:
- audits configured targets locally
- refreshes local dashboard artifacts
- serves the dashboard locally
- does not publish remotely
- does not enable auto-fix
- does not enable unattended workflows

Options:
  --targets name1,name2   Run only the listed configured target names
  --port 8070             Serve the dashboard on this port (default: 8070)
  --no-serve              Audit + refresh only, do not start the local server
  --list-targets          Show configured targets and exit
  -h, --help              Show this help

Examples:
  scripts/run-safe-local-backoffice.sh
  scripts/run-safe-local-backoffice.sh --targets fuel,selah
  scripts/run-safe-local-backoffice.sh --targets back-office --no-serve
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --targets)
      TARGETS="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --no-serve)
      NO_SERVE=true
      shift
      ;;
    --list-targets)
      LIST_ONLY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

cd "$ROOT"

export BACK_OFFICE_ENABLE_REMOTE_SYNC=0
export BACK_OFFICE_ENABLE_AUTOFIX=0
export BACK_OFFICE_ENABLE_UNATTENDED=0

if [[ "$LIST_ONLY" == true ]]; then
  python3 -m backoffice list-targets
  exit 0
fi

echo "== Safe Local Back Office Run =="
echo "Root: $ROOT"
echo "Remote sync: disabled"
echo "Auto-fix: disabled"
echo "Unattended workflows: disabled"
echo

echo "== Configured Targets =="
python3 -m backoffice list-targets
echo

echo "== Running Audits =="
if [[ -n "$TARGETS" ]]; then
  python3 -m backoffice audit-all --targets "$TARGETS"
else
  python3 -m backoffice audit-all
fi
echo

echo "== Refreshing Local Dashboard Artifacts =="
python3 -m backoffice refresh
echo

if [[ "$NO_SERVE" == true ]]; then
  echo "Local refresh complete. Dashboard not started because --no-serve was set."
  exit 0
fi

echo "== Starting Local Dashboard =="
echo "Open: http://127.0.0.1:$PORT/index.html"
exec python3 -m backoffice serve --port "$PORT"
