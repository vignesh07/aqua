# Aqua TODO - Based on v0.1 Testing Feedback

## Completed

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

---

## Lower Priority (Nice to Have)

### 6. Blocking agent-to-agent messages
**Problem**: `aqua msg` is fire-and-forget; can't ask and wait for response.

**Solution**:
```bash
aqua ask "Should I use Redis or SQLite?" --to worker-2 --wait
# Blocks until worker-2 responds with:
aqua reply <msg_id> "Use SQLite"
```
- Adds `reply_to` field to messages
- `--wait` polls for response with timeout

---

### 7. Headless/JSON mode for AI agents
**Problem**: Pretty terminal output is hard for AI agents to parse.

**Solution**:
- Already have `--json` on most commands
- Add `AQUA_JSON=1` env var to make JSON the default
- Ensure ALL commands support `--json` consistently

---

### 8. Background agent spawning worked via Claude's Task tool
**Note**: This actually worked! Claude spawned background agents using its own Task tool.
Consider documenting this as the recommended approach for Claude specifically.

---

## Summary

| Priority | Issue | Status |
|----------|-------|--------|
| HIGH | Agent ID not persisting after join | DONE |
| HIGH | `aqua spawn` AppleScript broken | DONE |
| MED | Task dependencies | DONE |
| MED | File locking | DONE |
| MED | Subagent monitoring/logs | DONE |
| LOW | Blocking messages | TODO |
| LOW | Global JSON mode | TODO |
