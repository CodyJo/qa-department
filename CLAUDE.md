# QA Department — Claude Code Instructions

This is an automated QA pipeline built for Claude Code. It uses two agent loops:

1. **QA Agent** — Scans a target repository for bugs, security issues, and performance problems
2. **Fix Agent** — Picks up findings, fixes them in isolated git worktrees, tests, and commits

## Project Structure

```
agents/           — Shell scripts that launch Claude Code agents
agents/prompts/   — System prompts for each agent type
config/           — Target repo configuration (gitignored)
dashboard/        — Static HTML dashboard (qa.html)
results/          — Findings and fix status (gitignored, synced to S3)
scripts/          — Setup, deploy, and cron scripts
terraform/        — AWS infrastructure (S3 + CloudFront)
lib/              — Format specs and severity definitions
```

## How It Works

1. `agents/qa-scan.sh <target-repo-path>` launches a Claude Code session that:
   - Reads the target repo's code
   - Runs linter, tests, and security analysis
   - Writes findings to `results/<repo-name>/findings.json`
   - Syncs dashboard data to S3

2. `agents/fix-bugs.sh <target-repo-path>` launches a Claude Code session that:
   - Reads `results/<repo-name>/findings.json`
   - Prioritizes by severity (critical > high > medium > low)
   - Fixes each issue in an isolated git worktree
   - Runs tests and linter in the worktree
   - Merges fixes back to main branch
   - Updates `results/<repo-name>/fixes.json`
   - Syncs dashboard data to S3

## Commands

- `make qa TARGET=/path/to/repo` — Run QA scan
- `make fix TARGET=/path/to/repo` — Run fix agent
- `make dashboard` — Deploy dashboard to S3
- `make setup` — Initial AWS setup via Terraform
