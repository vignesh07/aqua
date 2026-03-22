# Aqua Design Document

**Autonomous QUorum of Agents**

Version: 0.5.x (implementation snapshot)
Status: Current
Author: Vignesh
Last updated: 2026-03-22

---

## 1) Executive Summary

Aqua is a lightweight, agent-agnostic coordinator for CLI AI agents (Claude Code, Codex CLI, Gemini CLI, and generic CLIs) working in the same repository.

Aqua provides:
- Shared task queue with priorities and dependencies
- Atomic task claiming
- Heartbeat + leader lease for coordination/recovery
- File locking to reduce edit conflicts
- Agent-to-agent messaging (`msg`, `ask`, `reply`)
- Monitoring and recovery tools (`status`, `watch`, `logs`, `doctor`, `recover`)
- Agent orchestration (`spawn`, `ps`, `kill`, optional worktrees)
- Long-running workflow support (`serialize` + `spawn --loop`)
- Observer/Informer project memory (`observe`, `inform`)

Primary storage is SQLite (`.aqua/aqua.db`) in WAL mode, so setup remains local and dependency-light.

---

## 2) Goals and Non-Goals

### Goals

1. Coordinate multiple CLI agents in one codebase without external infra.
2. Prevent duplicate work via atomic claiming.
3. Recover from agent crashes with heartbeat and process checks.
4. Keep a simple and scriptable CLI interface.
5. Stay agent-agnostic and provider-agnostic.

### Non-Goals

1. Distributed/multi-machine consensus.
2. Strict security isolation between local agents.
3. Real-time streaming transport (polling + local DB is sufficient).
4. Full web product surface (CLI-first tool).

---

## 3) Current Architecture

```text
User / AI Agents
   ↓
Aqua CLI (Click + Rich)
   ↓
Coordinator Logic (claiming, leader lease, recovery)
   ↓
SQLite (.aqua/aqua.db, WAL mode)
```

### Core runtime components

- **CLI layer (`src/aqua/cli.py`)**
  - Command parsing, UX, JSON output mode, orchestration behavior.
- **Database layer (`src/aqua/db.py`)**
  - Schema, migrations, transactional updates, query helpers.
- **Coordinator (`src/aqua/coordinator.py`)**
  - Claiming logic, dead agent detection, stale task recovery.
- **Models (`src/aqua/models.py`)**
  - Typed dataclasses for Agent, Task, Message, Leader, Event.
- **Utilities (`src/aqua/utils.py`)**
  - Time/process helpers, naming helpers.

---

## 4) Repository and Runtime Layout

### Repository (current)

```text
.
├── DESIGN.md
├── README.md
├── TODO.md
├── pyproject.toml
├── src/aqua/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── coordinator.py
│   ├── db.py
│   ├── models.py
│   ├── utils.py
│   └── templates/AGENT_INSTRUCTIONS.md
└── tests/
    ├── conftest.py
    ├── test_coordinator.py
    ├── test_db.py
    └── test_leader.py
```

### Per-project runtime state

```text
.aqua/
├── aqua.db
├── aqua.db-wal
├── aqua.db-shm
├── sessions/
├── summary.md              # observer output
└── observer_state.json     # observer cursor
```

---

## 5) CLI Surface (current)

### Core
- `aqua init`
- `aqua status`
- `aqua refresh`

### Tasks
- `aqua add`
- `aqua list`
- `aqua show`
- `aqua claim`
- `aqua done`
- `aqua fail`
- `aqua progress`
- `aqua serialize`

### Agents and orchestration
- `aqua join`
- `aqua leave`
- `aqua spawn`
- `aqua ps`
- `aqua kill`
- `aqua worktree`

### Communication
- `aqua msg`
- `aqua inbox`
- `aqua ask`
- `aqua reply`

### File locking
- `aqua lock`
- `aqua unlock`
- `aqua locks`

### Monitoring / recovery
- `aqua watch`
- `aqua log`
- `aqua logs`
- `aqua doctor`
- `aqua recover`

### Setup and context persistence
- `aqua setup`
- `aqua observe`
- `aqua inform`

All major commands support `--json`; global JSON mode is available via `AQUA_JSON=1`.

---

## 6) Data Model

Primary entities:
- **Agent**: identity, type, status, heartbeat, current task, optional role.
- **Task**: priority, status, claim info, retries, tags, context, dependencies.
- **Message**: broadcast/direct messages, questions/replies.
- **Leader**: current lease owner + fencing term.
- **Event**: audit log of agent/task/system actions.
- **FileLock**: per-file exclusive lock by agent.

### Task lifecycle

`pending → claimed → done`
`pending → claimed → failed`
`pending → claimed → abandoned → pending` (if retry budget remains)

### Agent lifecycle

`active → dead` (via recovery)

---

## 7) Database Schema (SQLite)

Schema version: **4** (`schema_version` table).

Tables:
- `agents`
- `leader` (single-row lease record)
- `tasks`
- `messages`
- `events`
- `file_locks`
- `schema_version`

Important schema features:
- WAL mode + busy timeout for concurrent CLI processes.
- `tasks.depends_on` stores JSON array of task IDs.
- `messages.reply_to` enables `ask/reply` threading.
- `agents.last_progress` and `agents.role` support refresh and role-aware selection.
- `file_locks.file_path` as primary key enforces exclusivity.

Migrations currently handled in `db._run_migrations()`:
- v1 → v2: `agents.last_progress`, `agents.role`
- v2 → v3: `tasks.depends_on`
- v3 → v4: `messages.reply_to` + index

---

## 8) Core Algorithms and Flows

### 8.1 Atomic task claim

Claiming uses a transaction (`BEGIN IMMEDIATE`) to update both:
1. task row (`pending -> claimed`, claimant, timestamp, term)
2. agent row (`current_task_id`)

This prevents orphaned assignments on mid-operation crash.

### 8.2 Dependency-aware scheduling

- Default scheduler picks highest-priority, oldest `pending` task.
- Task is claimable only when all `depends_on` tasks are `done`.
- Cycle detection (`would_create_cycle`) prevents invalid dependency graphs.

### 8.3 Role-aware scheduling

When agent has a role:
1. try pending tasks tagged with that role
2. if none available/claimable, fallback to general pending tasks

### 8.4 Leader election with lease + term

- Leader row holds `agent_id`, `term`, and `lease_expires_at`.
- Agent renews if already leader.
- Expired lease can be taken over with term increment (fencing token pattern).

### 8.5 Recovery

Coordinator recovery cycle:
1. find stale-heartbeat active agents
2. verify process liveness (PID check)
3. mark dead agents
4. abandon their claimed tasks
5. requeue abandoned tasks below `max_retries`
6. reclaim stale long-claimed tasks (timeout)

Default thresholds (current code):
- agent dead threshold: 300s
- task claim timeout: 1800s

### 8.6 Serialize + loop workflow

- `serialize` topologically orders pending tasks and inserts checkpoint tasks.
- `spawn --loop` (single-agent background mode) respawns fresh agent sessions at checkpoint boundaries to keep context fresh for long projects.

### 8.7 Observer / Informer

- `observe` periodically summarizes recent events/tasks/progress/git diff to `.aqua/summary.md`.
- `inform` returns this accumulated context to workers/users.
- Current implementation is summary-first; future versions may add LLM-native answering.

---

## 9) Reliability and Failure Handling

Handled scenarios:
- Agent process death: detected and recovered.
- Stale task claims: abandoned and requeued (retry-limited).
- Claim races: transactional claim + status guard.
- Leader loss: lease expiry + takeover.
- File lock conflicts: atomic PK constraint prevents dual lock.

Known practical constraints:
- Local-machine coordination model.
- PID checks are best-effort.
- Very large queues may benefit from more SQL-native dependency resolution.

---

## 10) Security Model

Aqua assumes trusted local execution.

- No auth layer between local agents.
- Background spawn modes can run agents with powerful CLI flags.
- Users must treat spawned agent processes as privileged local automations.

For this reason, `spawn -b` includes warning/confirmation behavior.

---

## 11) Configuration and Integration

- Runtime DB location: `.aqua/aqua.db`
- Global JSON output: `AQUA_JSON=1`
- Setup command writes agent instructions to:
  - `CLAUDE.md`
  - `AGENTS.md`
  - `GEMINI.md`

CLI integration is intentionally minimal: Aqua coordinates through commands and shared DB state rather than deep provider-specific APIs.

---

## 12) Testing Strategy (current)

Current test modules:
- `tests/test_db.py`
- `tests/test_coordinator.py`
- `tests/test_leader.py`

Focus areas:
- schema and migrations
- claim/recovery behavior
- leader lease semantics

---

## 13) Open Design Work

Current roadmap themes (see `TODO.md`):
- Further performance tuning for dependency resolution
- Continued CLI modularization (`cli.py` is large)
- Cross-platform process-detection robustness
- Expanded conflict-resolution and monitoring features

---

## 14) Change Log for This Document

This revision updates prior design text to match current implementation by:
- Replacing outdated command inventory (including removed `daemon` references)
- Aligning module/test tree with current repository
- Documenting implemented features: dependencies, file locks, ask/reply, serialize/loop, observer/informer, role-aware claiming
- Aligning schema/migration details with `SCHEMA_VERSION = 4`
