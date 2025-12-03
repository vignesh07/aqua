# Aqua Roadmap

## Completed (v0.2.3)

### v0.2.3
- Added "Let the Agent Do It" workflow to README and docs
- Updated author info for PyPI

### v0.2.2
- Heartbeat-based orphan task recovery (auto-recovers tasks from dead agents)
- Spawn validation - waits for agents to join before reporting success
- Fixed Codex CLI flags (use `exec --full-auto` instead of `--approval-mode`)
- Extended timeouts: 5min heartbeat, 30min task claim (for LLM operations)
- Round-robin CLI assignment (`aqua spawn 4 --claude --codex` alternates)
- Background mode confirmation prompt with `-y` skip flag
- Enhanced AGENT_INSTRUCTIONS.md with 8 coordination patterns

## Completed (v0.2.0)

### 1. ~~Fix agent ID persistence after `aqua join`~~ DONE
- Changed from PPID-based to "default" session for AI agents without TTY
- Agent ID now persists correctly and `aqua refresh` works immediately after join

### 2. ~~Fix `aqua spawn` - AppleScript syntax error~~ DONE
- Fixed by writing prompt to temp file instead of escaping in AppleScript
- Avoids all quote/newline escaping issues

### 3. ~~Task dependencies~~ DONE
- Added `--depends-on <task_id>` and `--after "title"` options to `aqua add`
- `claim` automatically skips tasks with unmet dependencies
- `aqua show` displays blocking dependencies

### 4. ~~File locking/claiming~~ DONE
- Added `aqua lock <file>`, `aqua unlock <file>`, `aqua locks` commands
- New `file_locks` table with atomic locking via PRIMARY KEY constraint
- Locks released when agent leaves

### 5. ~~Monitoring subagents~~ DONE
- Added `aqua logs` command for real-time event tailing (like `tail -f`)
- Supports `--agent NAME` and `--task ID` filtering
- `--json` flag for machine-readable output

### 6. ~~Blocking agent-to-agent messages~~ DONE
- Added `aqua ask "question" --to agent --timeout 60`
- Added `aqua reply <msg_id> "answer"`
- Questions block until reply received or timeout

### 7. ~~Global JSON mode~~ DONE
- Added `AQUA_JSON=1` env var to enable JSON output globally
- All commands now support `--json` flag consistently

### 8. ~~Multi-CLI support~~ DONE
- Added support for Claude Code, Codex CLI, Gemini CLI
- `aqua setup --claude`, `--codex`, `--gemini`, `--all`
- `aqua spawn` auto-detects available CLI or use `--cli` to specify

---

## Roadmap

### Performance & Reliability (High Priority)

#### Atomic claim transactions
- `claim_task` and `update_agent_task` are separate statements
- A crash between them could orphan the assignment
- **Fix**: Move both updates into a single DB transaction
- Files: `src/aqua/coordinator.py:28`, `src/aqua/db.py:371`

#### SQL-based dependency resolution
- `get_next_pending_task` fetches all pending tasks, checks deps in Python
- Gets expensive as queues grow (O(n) per claim)
- **Fix**: Push dependency resolution into SQL (join table or materialized view)
- File: `src/aqua/db.py:332`

#### Graceful shutdown
- Add signal handlers for SIGTERM/SIGINT
- Release file locks and orphan current task on shutdown
- Prevents stuck tasks when agents are killed

### Code Quality (Medium Priority)

#### Split CLI module
- `cli.py` is ~2.5K lines, hard to navigate and test
- **Fix**: Split into topical modules: `tasks.py`, `agents.py`, `comms.py`, `locks.py`, `spawn.py`
- Enables focused unit tests per command group
- File: `src/aqua/cli.py`

#### Fix datetime deprecation warnings
- Replace `datetime.utcnow()` with `datetime.now(datetime.UTC)`
- Affects: `coordinator.py`, `db.py`, `models.py`, tests

### Cross-Platform (Low Priority)

#### Portable process detection
- `os.kill(pid, 0)` is POSIX-only, inconsistent on Windows
- PID recycling can cause false positives
- **Fix**: Abstract per-platform or use UUID-based heartbeats
- File: `src/aqua/utils.py:36`

### Future Ideas

#### Better conflict resolution
- Automatic git merge conflict detection
- Suggest which agent should handle conflicts

#### Web dashboard
- Real-time web UI for monitoring
- Task Kanban board

#### Distributed mode
- Support for agents on different machines
- Replace SQLite with PostgreSQL/Redis

---

## Summary

| Feature | Status |
|---------|--------|
| Agent ID persistence | DONE |
| `aqua spawn` AppleScript | DONE |
| Task dependencies | DONE |
| File locking | DONE |
| Subagent monitoring/logs | DONE |
| Blocking messages | DONE |
| Global JSON mode | DONE |
| Multi-CLI support | DONE |
