# Dual-Backend Orchestrator — Design Spec

**Date:** 2026-03-22
**Status:** Approved
**Scope:** Evolve Back Office from single-backend (Claude) to dual-backend (Claude + Codex) with live capability/limit checks and intelligent task routing.

---

## Problem

Back Office currently hardcodes Claude as the only AI backend. The system should be able to use Claude and Codex concurrently — sending planning/synthesis work to Claude and bounded implementation work to Codex — based on live capability checks, not vendor assumptions.

## Current State

The codebase is **already 90% decoupled**:
- All 10 agent scripts call `scripts/run-agent.sh` with standard params (`--prompt`, `--tools`, `--repo`)
- Config schema (`RunnerConfig`) is generic (command + mode)
- `setup.py` already knows about claude, codex, and aider
- Both API servers launch agents via subprocess with no backend logic

**Only coupling point**: `run-agent.sh` has hardcoded CLI flags for `claude-print` mode and `stdin-text` mode.

## Design

### Architecture

```
backoffice/
  backends/
    __init__.py         — Backend registry + get_backend()
    base.py             — Abstract backend interface
    claude.py           — Claude adapter (health, capabilities, limits, invoke)
    codex.py            — Codex adapter (health, capabilities, limits, invoke)
    limits.py           — Normalized limit model
  router.py             — Task routing: checks backends, assigns work
config/
  backoffice.yaml       — Updated with agent_backends section
scripts/
  run-agent.sh          — Updated to accept --backend flag, delegates to Python
```

### Backend Interface

```python
class Backend(ABC):
    name: str

    def health_check(self) -> HealthStatus
    def capabilities(self) -> dict[str, bool]
    def check_limits(self) -> LimitState
    def invoke(self, prompt: str, tools: list[str], repo_dir: str) -> str
```

### Capability Contract

Normalized capabilities each backend advertises:
- `read_files`, `search_code`, `edit_files`, `write_files`
- `run_shell`, `structured_output`, `multi_file_refactor`
- `long_context_reasoning`, `subagents`, `commit_changes`

### Limit Contract

```python
@dataclass
class LimitState:
    backend: str
    status: str  # healthy | degraded | unavailable
    supports_structured_output: bool
    context_window_tokens: int
    rate_limit_state: str  # ok | near_limit | limited | unknown
    usage_state: str  # ok | near_plan_limit | limited | unknown
    recommended_parallelism: int
    notes: list[str]
```

### Router

```python
def assign_backend(task_type: str, task_requirements: dict) -> Assignment:
    # 1. Check all backends health + limits
    # 2. Match task requirements to capabilities
    # 3. Apply routing policy from config
    # 4. Return assignment with reason
```

### Config

```yaml
agent_backends:
  claude:
    enabled: true
    command: "claude"
    model: "haiku"
    mode: "claude-print"
    local_budget:
      max_parallel_tasks: 2
      max_context_tokens: 200000

  codex:
    enabled: false  # opt-in
    command: "codex"
    model: "codex"
    mode: "stdin-text"
    local_budget:
      max_parallel_tasks: 4
      max_context_tokens: 150000

routing_policy:
  prefer_claude_for: [prioritize_backlog, summarize_cycle, audit_repo]
  prefer_codex_for: [fix_finding, implement_feature]
  fallback_order:
    prioritize_backlog: [claude, codex]
    implement_feature: [codex, claude]
    fix_finding: [codex, claude]
    audit_repo: [claude, codex]
```

### Backward Compatibility

- When only `runner:` is configured (current format), the system operates in single-backend mode using that runner — zero behavior change
- `agent_backends:` is optional. When present, it overrides `runner:`
- `run-agent.sh` gains an optional `--backend` flag. Without it, uses the default backend from config

### Integration with Overnight Loop

The overnight loop's Product Owner runs on Claude (planning/synthesis). Fix and feature tasks route through the router, which may send them to Codex if it's enabled and healthy.

## Implementation Sequence

1. **Backend base + adapters** — Python classes for Claude and Codex
2. **Limit checking** — Health check, capability report, limit state
3. **Router** — Task assignment based on capabilities + limits + policy
4. **Config update** — `agent_backends` section in backoffice.yaml
5. **run-agent.sh update** — Accept `--backend` flag, delegate invocation to Python
6. **Overnight loop integration** — Router assigns backends per task
7. **Tests** — Adapter checks, routing, fallback behavior
