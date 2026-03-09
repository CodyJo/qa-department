#!/usr/bin/env bash
# QA Department — Scan Agent
# Usage: ./agents/qa-scan.sh /path/to/target-repo [--sync]
#
# Launches a Claude Code session that scans the target repository
# for bugs, security issues, and performance problems.
#
# Options:
#   --sync    Sync results to S3 after scan completes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QA_ROOT="$(dirname "$SCRIPT_DIR")"
PROMPT_FILE="$SCRIPT_DIR/prompts/qa-scan.md"
CONFIG_FILE="$QA_ROOT/config/qa-config.yaml"

# ── Args ─────────────────────────────────────────────────────────────────────

TARGET_REPO="${1:?Usage: qa-scan.sh /path/to/target-repo [--sync]}"
SYNC_TO_S3=false

for arg in "$@"; do
  case "$arg" in
    --sync) SYNC_TO_S3=true ;;
  esac
done

# Validate target
if [ ! -d "$TARGET_REPO/.git" ]; then
  echo "Error: $TARGET_REPO is not a git repository" >&2
  exit 1
fi

REPO_NAME="$(basename "$TARGET_REPO")"
RESULTS_DIR="$QA_ROOT/results/$REPO_NAME"
mkdir -p "$RESULTS_DIR"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║  QA Department — Scanning: $REPO_NAME"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Target:  $TARGET_REPO"
echo "  Results: $RESULTS_DIR"
echo "  Time:    $(date -Iseconds)"
echo ""

# ── Read config for lint/test commands ────────────────────────────────────────

LINT_CMD=""
TEST_CMD=""
CONTEXT=""

if command -v python3 &>/dev/null && [ -f "$QA_ROOT/config/targets.yaml" ]; then
  # Extract target-specific config using python
  eval "$(python3 -c "
import yaml, sys
with open('$QA_ROOT/config/targets.yaml') as f:
    cfg = yaml.safe_load(f)
for t in cfg.get('targets', []):
    if t['name'] == '$REPO_NAME' or t.get('path','') == '$TARGET_REPO':
        print(f'LINT_CMD={repr(t.get(\"lint_command\",\"\"))}')
        print(f'TEST_CMD={repr(t.get(\"test_command\",\"\"))}')
        print(f'CONTEXT={repr(t.get(\"context\",\"\"))}')
        break
" 2>/dev/null || true)"
fi

# ── Build the prompt ─────────────────────────────────────────────────────────

SCAN_PROMPT="$(cat "$PROMPT_FILE")

---

## Target Repository

- **Path:** $TARGET_REPO
- **Name:** $REPO_NAME
- **Results directory:** $RESULTS_DIR

## Commands

- **Lint:** ${LINT_CMD:-"(auto-detect from project config)"}
- **Test:** ${TEST_CMD:-"(auto-detect from project config)"}

## Additional Context

${CONTEXT:-"No additional context provided. Read the project's README and CLAUDE.md for context."}

## Instructions

1. cd to $TARGET_REPO
2. Read the project structure and understand the codebase
3. Run linter and tests, capture output
4. Perform security audit, input validation check, performance review, and code quality review
5. Write all findings to: $RESULTS_DIR/findings.json
6. Write a human-readable summary to: $RESULTS_DIR/scan-summary.md
7. Generate dashboard data: $RESULTS_DIR/dashboard.json

Start the scan now."

# ── Launch Claude Code ───────────────────────────────────────────────────────

echo "Launching Claude Code scan agent..."
echo ""

claude --print "$SCAN_PROMPT" \
  --allowedTools "Read,Glob,Grep,Bash,Write,Agent" \
  --additionalDirectories "$TARGET_REPO"

echo ""
echo "Scan complete. Results in: $RESULTS_DIR/"

# ── Sync to S3 if requested ─────────────────────────────────────────────────

if [ "$SYNC_TO_S3" = true ]; then
  echo "Syncing results to S3..."
  bash "$SCRIPT_DIR/../scripts/sync-dashboard.sh" 2>/dev/null || echo "Warning: S3 sync failed"
fi

echo ""
echo "Done."
