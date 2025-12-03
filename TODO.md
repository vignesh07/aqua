# Aqua TODO - Based on v0.1 Testing Feedback

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

## Future Ideas

### Better conflict resolution
- Automatic git merge conflict detection
- Suggest which agent should handle conflicts

### Web dashboard
- Real-time web UI for monitoring
- Task Kanban board

### Distributed mode
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
